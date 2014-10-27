"""
This block defines a Staff Graded Assignment.  Students are shown a rubric
and invited to upload a file which is then graded by staff.
"""
import datetime
import hashlib
import json
import logging
import mimetypes
import os
import pkg_resources
import pytz

from functools import partial

from courseware.models import StudentModule

from django.core.files import File
from django.core.files.storage import default_storage
from django.template import Context, Template

from webob.response import Response

from xblock.core import XBlock
from xblock.fields import Boolean, DateTime, Scope, String, Float, Dict
from xblock.fragment import Fragment

from xmodule.util.duedate import get_extended_due_date

from collections import namedtuple

from zipfile import ZipFile
from tempfile import NamedTemporaryFile

log = logging.getLogger(__name__)

FileMetaData = namedtuple('FileMetaData', 'filename mimetype timestamp')

class StaffGradedAssignmentXBlock(XBlock):
    """
    This block defines a Staff Graded Assignment.  Students are shown a rubric
    and invited to upload a file which is then graded by staff.
    """
    has_score = True
    icon_class = 'problem'

    display_name = String(
        default='Staff Graded Assignment', scope=Scope.settings,
        help="This name appears in the horizontal navigation at the top of "
             "the page."
    )

    weight = Float(
        display_name="Problem Weight",
        help=("Defines the number of points each problem is worth. "
              "If the value is not set, the problem is worth the sum of the "
              "option point values."),
        values={"min": 0, "step": .1},
        scope=Scope.settings
    )

    points = Float(
        display_name="Maximum score",
        help=("Maximum grade score given to assignment by staff."),
        values={"min": 0, "step": .1},
        default=100,
        scope=Scope.settings
    )

    score = Float(
        display_name="Grade score",
        default=None,
        help=("Grade score given to assignment by staff."),
        values={"min": 0, "step": .1},
        scope=Scope.user_state
    )

    score_published = Boolean(
        display_name="Whether score has been published.",
        help=("This is a terrible hack, an implementation detail."),
        default=True,
        scope=Scope.user_state
    )

    score_approved = Boolean(
        display_name="Whether the score has been approved by an instructor",
        help=("Course staff may submit grades but an instructor must approve "
              "grades before they become visible."),
        default=False,
        scope=Scope.user_state
    )

    comment = String(
        display_name="Instructor comment",
        default='',
        scope=Scope.user_state,
        help="Feedback given to student by instructor."
    )

    uploaded_files = Dict(
        display_name="Uploaded Files",
        scope=Scope.user_state,
        default=dict(),
        help="Files uploaded by the user. Tuple of filename, mimetype and timestamp"
    )

    uploaded_files_last_timestamp = String(
        display_name="Submitted",
        scope=Scope.user_state,
        default=None,
        help="The time and date the student last uploaded a file."
    )

    annotated_sha1 = String(
        display_name="Annotated SHA1",
        scope=Scope.user_state,
        default=dict(),
        help=("sha1 of the annotated file uploaded by the instructor for "
              "this assignment.")
    )

    annotated_filename = String(
        display_name="Annotated file name",
        scope=Scope.user_state,
        default=None,
        help="The name of the annotated file uploaded for this assignment."
    )

    annotated_mimetype = String(
        display_name="Mime type of annotated file",
        scope=Scope.user_state,
        default=None,
        help="The mimetype of the annotated file uploaded for this assignment."
    )

    annotated_timestamp = DateTime(
        display_name="Timestamp",
        scope=Scope.user_state,
        default=None,
        help="When the annotated file was uploaded")

    def max_score(self):
        return self.points

    def student_view(self, context=None):
        """
        The primary view of the StaffGradedAssignmentXBlock, shown to students
        when viewing courses.
        """
        # Ideally we would do this when the score is entered.  This write on
        # read pattern is pretty bad.  Currently, though, the code in the
        # courseware application that handles the grade event will puke if the
        # user_id for the event is other than the logged in user.
        if not self.score_published and self.score_approved:
            self.runtime.publish(self, 'grade', {
                'value': self.score,
                'max_value': self.max_score(),
            })
            self.score_published = True

        context = {
            "student_state": json.dumps(self.student_state()),
            "id": self.location.name.replace('.', '_')
        }
        if self.show_staff_grading_interface():
            context['is_course_staff'] = True
            self.update_staff_debug_context(context)

        fragment = Fragment()
        fragment.add_content(
            render_template(
                'templates/staff_graded_assignment/show.html',
                context
            )
        )
        fragment.add_css(_resource("static/css/edx_sga.css"))
        fragment.add_javascript(_resource("static/js/src/edx_sga.js"))
        fragment.initialize_js('StaffGradedAssignmentXBlock')
        return fragment

    def update_staff_debug_context(self, context):
        published = self.published_date
        context['is_released'] = published and published < _now()
        context['location'] = self.location
        context['category'] = type(self).__name__
        context['fields'] = [
            (name, field.read_from(self))
            for name, field in self.fields.items()]

    def student_state(self):
        """
        Returns a JSON serializable representation of student's state for
        rendering in client view.
        """

        uploaded = []
        for sha1, metadata in self.uploaded_files.iteritems():
            metadata = FileMetaData._make(metadata)
            uploaded.append({"sha1": sha1, "filename": metadata.filename})

        if self.annotated_sha1:
            annotated = {"filename": self.annotated_filename}
        else:
            annotated = None

        if self.score is not None and self.score_approved:
            graded = {'score': self.score, 'comment': self.comment}
        else:
            graded = None

        return {
            "uploaded": uploaded,
            "annotated": annotated,
            "graded": graded,
            "max_score": self.max_score(),
            "published": self.score_published,
            "upload_allowed": self.upload_allowed(),
        }

    def staff_grading_data(self):
        def get_student_data(module):
            state = json.loads(module.state)
            instructor = self.is_instructor()
            score = state.get('score')
            approved = state.get('score_approved')

            metadatalist = state.get("uploaded_files")

            uploaded = []
            for sha1, metadata in metadatalist.iteritems():
                metadata = FileMetaData._make(metadata)
                uploaded.append({
                    "sha1": sha1, 
                    "filename": metadata.filename,
                    "timestamp": metadata.timestamp
                })


            return {
                'module_id': module.id,
                'username': module.student.username,
                'fullname': module.student.profile.name,
                'uploaded': uploaded,
                #'filename': state.get("uploaded_filename"),
                'timestamp': state.get("uploaded_files_last_timestamp"),
                'published': state.get("score_published"),
                'score': score,
                'approved': approved,
                'needs_approval': instructor and score is not None
                                  and not approved,
                'may_grade': instructor or not approved,
                'annotated': state.get("annotated_filename"),
                'comment': state.get("comment", ''),
            }

        query = StudentModule.objects.filter(
            course_id=self.xmodule_runtime.course_id,
            module_state_key=self.location
        )

        return {
            'assignments': [get_student_data(module) for module in query],
            'max_score': self.max_score(),
        }

    def studio_view(self, context=None):
        try:
            cls = type(self)

            def none_to_empty(x):
                return x if x is not None else ''
            edit_fields = (
                (field, none_to_empty(getattr(self, field.name)), validator)
                for field, validator in (
                    (cls.display_name, 'string'),
                    (cls.points, 'number'),
                    (cls.weight, 'number'))
            )

            context = {
                'fields': edit_fields
            }
            fragment = Fragment()
            fragment.add_content(
                render_template(
                    'templates/staff_graded_assignment/edit.html',
                    context
                )
            )
            fragment.add_javascript(_resource("static/js/src/studio.js"))
            fragment.initialize_js('StaffGradedAssignmentXBlock')
            return fragment
        except:  # pragma: NO COVER
            log.error("Don't swallow my exceptions", exc_info=True)
            raise

    @XBlock.json_handler
    def save_sga(self, data, suffix=''):
        for name in ('display_name', 'points', 'weight'):
            setattr(self, name, data.get(name, getattr(self, name)))

    @XBlock.handler
    def upload_assignment(self, request, suffix=''):
        assert self.upload_allowed()
        upload = request.params['assignment']

        uploaded_sha1 = _get_sha1(upload.file)

        metadata = FileMetaData(
            upload.file.name,
            mimetypes.guess_type(upload.file.name)[0],
            str( _now() )
        )

        self.uploaded_files_last_timestamp = metadata.timestamp

        self.uploaded_files[uploaded_sha1] = metadata

        path = _file_storage_path(
            self.location.to_deprecated_string(),
            uploaded_sha1,
            metadata.filename
        )

        if not default_storage.exists(path):
            default_storage.save(path, File(upload.file))
        return Response(json_body=self.student_state())

    @XBlock.handler
    def download_assignment(self, request, suffix=''):
        #temporory: return the first file.

        if (suffix not in self.uploaded_files):
            log.error("File download failure: No matching file belongs to this student.", exc_info=True)
            raise

        metadata = FileMetaData._make(self.uploaded_files[suffix])

        path = _file_storage_path(
            self.location.to_deprecated_string(),
            suffix, 
            metadata.filename
        )

        return self.download(
            path,
            metadata.mimetype,
            metadata.filename
        )

    @XBlock.handler
    def staff_download(self, request, suffix=''):
        assert self.is_course_staff()
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)

        if (suffix not in state['uploaded_files']):
            log.error("File download failure: No matching file belongs to this student.", exc_info=True)
            raise

        metadata = FileMetaData._make(state['uploaded_files'][suffix])

        path = _file_storage_path(
            module.module_state_key.to_deprecated_string(),
            suffix,
            metadata.filename
        )
        return self.download(
            path,
            metadata.mimetype,
            metadata.filename
        )

    #For downloading the entire assingment for one student.
    @XBlock.handler
    def staff_download_zipped(self, request, suffix=''):
        assert self.is_course_staff()
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)

        metadatalist = state['uploaded_files']

        if (len(metadatalist) == 0):
            res = Response()
            res.status = 204
            return res

        #file to be returned
        assignment = NamedTemporaryFile()
        #assignment.name = 'assignment.zip'
        assignment_zip = ZipFile(assignment, 'w')

        for sha1, metadata in metadatalist.iteritems():
            metadata = FileMetaData._make(metadata)
            path = _file_storage_path(
                self.location.to_deprecated_string(),
                sha1,
                metadata.filename
            )

            afile = default_storage.open(path)

            assignment_zip.writestr(metadata.filename, afile.read())

        #sha1 = _get_sha1(assignment_file)
        assignment_zip.save()
        assignment_zip.close()

        response = Response()
        response.mimetype = 'application/zip'
        response.body = assignment.read()
        response.content_disposition = 'attachment; filename=assignment.zip'

        assignment.close()
        return response


    @XBlock.handler
    def staff_upload_annotated(self, request, suffix=''):
        assert self.is_course_staff()
        upload = request.params['annotated']
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)
        state['annotated_sha1'] = sha1 = _get_sha1(upload.file)
        state['annotated_filename'] = filename = upload.file.name
        state['annotated_mimetype'] = mimetypes.guess_type(upload.file.name)[0]
        state['annotated_timestamp'] = _now().strftime(
            DateTime.DATETIME_FORMAT
        )
        path = _file_storage_path(
            self.location.to_deprecated_string(),
            sha1,
            filename
        )
        if not default_storage.exists(path):
            default_storage.save(path, File(upload.file))
        module.state = json.dumps(state)
        module.save()
        return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def download_annotated(self, request, suffix=''):
        path = _file_storage_path(
            self.location.to_deprecated_string(),
            self.annotated_sha1,
            self.annotated_filename
        )
        return self.download(
            path,
            self.annotated_mimetype,
            self.annotated_filename
        )

    @XBlock.handler
    def staff_download_annotated(self, request, suffix=''):
        assert self.is_course_staff()
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)
        path = _file_storage_path(
            module.module_state_key.to_deprecated_string(),
            state['annotated_sha1'],
            state['annotated_filename']
        )
        return self.download(
            path,
            state['annotated_mimetype'],
            state['annotated_filename']
        )

    @XBlock.handler
    def delete_assignment(self, request, suffix=''):
        if suffix in self.uploaded_files:
            metadata = FileMetaData._make(self.uploaded_files[suffix])

            path = _file_storage_path(
                self.location.to_deprecated_string(),
                suffix,
                metadata.filename
            )

            default_storage.delete(path)
            del self.uploaded_files[suffix]

        res = Response()
        res.status = 204
        return res


    def download(self, path, mimetype, filename):
        BLOCK_SIZE = 2**10 * 8  # 8kb
        file = default_storage.open(path)
        app_iter = iter(partial(file.read, BLOCK_SIZE), '')
        return Response(
            app_iter=app_iter,
            content_type=mimetype,
            content_disposition="attachment; filename=" + filename)

    @XBlock.handler
    def get_staff_grading_data(self, request, suffix=''):
        assert self.is_course_staff()
        return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def enter_grade(self, request, suffix=''):
        assert self.is_course_staff()
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)
        state['score'] = float(request.params['grade'])
        state['comment'] = request.params.get('comment', '')
        state['score_published'] = False    # see student_view
        state['score_approved'] = self.is_instructor()
        module.state = json.dumps(state)

        # This is how we'd like to do it.  See student_view
        # self.runtime.publish(self, 'grade', {
        #     'value': state['score'],
        #     'max_value': self.max_score(),
        #     'user_id': module.student.id
        # })

        module.save()
        return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def remove_grade(self, request, suffix=''):
        assert self.is_course_staff()
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)
        state['score'] = None
        state['comment'] = ''
        state['score_published'] = False    # see student_view
        state['score_approved'] = False
        state['annotated_sha1'] = None
        state['annotated_filename'] = None
        state['annotated_mimetype'] = None
        state['annotated_timestamp'] = None
        module.state = json.dumps(state)
        module.save()
        return Response(json_body=self.staff_grading_data())

    def is_course_staff(self):
        return getattr(self.xmodule_runtime, 'user_is_staff', False)

    def is_instructor(self):
        return self.xmodule_runtime.get_user_role() == 'instructor'

    def show_staff_grading_interface(self):
        in_studio_preview = self.scope_ids.user_id is None
        return self.is_course_staff() and not in_studio_preview

    def past_due(self):
        due = get_extended_due_date(self)
        if due is not None:
            return _now() > due
        return False

    def upload_allowed(self):
        return not self.past_due() and self.score is None



def _file_storage_path(url, sha1, filename):
    assert url.startswith("i4x://")
    path = url[6:] + '/' + sha1
    path += os.path.splitext(filename)[1]
    return path


def _get_sha1(file):
    BLOCK_SIZE = 2**10 * 8  # 8kb
    sha1 = hashlib.sha1()
    for block in iter(partial(file.read, BLOCK_SIZE), ''):
        sha1.update(block)
    file.seek(0)

    sha1.update(str(_now()))
    return sha1.hexdigest()


def _resource(path):  # pragma: NO COVER
    """Handy helper for getting resources from our kit."""
    data = pkg_resources.resource_string(__name__, path)
    return data.decode("utf8")


def _now():
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)


def load_resource(resource_path):
    """
    Gets the content of a resource
    """
    resource_content = pkg_resources.resource_string(__name__, resource_path)
    return unicode(resource_content)


def render_template(template_path, context={}):
    """
    Evaluate a template by resource path, applying the provided context
    """
    template_str = load_resource(template_path)
    template = Template(template_str)
    return template.render(Context(context))
