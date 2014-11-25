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

from file_management_mixin import FileMetaData, FileManagementMixin, get_file_metadata
from file_submission_mixin import FileSubmissionMixin
from file_annotation_mixin import FileAnnotationMixin

from courseware.models import StudentModule

from django.core.files import File
#from django.core.files.storage import default_storage
from django.template import Context, Template

from webob.response import Response

from xblock.core import XBlock
from xblock.fields import Boolean, DateTime, Scope, String, Float, Dict
from xblock.fragment import Fragment

from xmodule.util.duedate import get_extended_due_date

log = logging.getLogger(__name__)

#FileMetaData = namedtuple('FileMetaData', 'filename mimetype timestamp')

class StaffGradedAssignmentXBlock(
    XBlock, 
    FileManagementMixin, 
    FileSubmissionMixin,
    FileAnnotationMixin):
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

    is_submitted = Boolean(
        display_name="Is Submitted",
        scope=Scope.user_state,
        default=False,
        help="Whether the student has submitted their work or not."
    )

    submission_time = String(
        display_name="Submission Time",
        scope=Scope.user_state,
        default=None,
        help="The time the user submitted the assignment for grading."
    )

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
        """
        Gathers information for the Staff Debug Info button on 
        the lms page.
        """
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

        annotated = []
        for sha1, metadata in self.annotated_files.iteritems():
            metadata = FileMetaData._make(metadata)
            annotated.append({"sha1": sha1, "filename": metadata.filename})

        if self.score is not None and self.score_approved:
            graded = {'score': self.score, 'comment': self.comment}
        else:
            graded = None

        return {
            "uploaded":        uploaded,
            "annotated":       annotated,

            "graded":          graded,
            "max_score":       self.max_score(),
            "published":       self.score_published,

            "upload_allowed":  self.upload_allowed(),
            "submitted":       self.is_submitted,
            "submission_time": str(self.submission_time)
        }

    def staff_grading_data(self):
        """
        Gathers data for display to staff using the Grade Submission
        button on the lms page.
        """
        def get_student_data(module):
            """
            Packages data from a student module for display to staff.
            """
            state = json.loads(module.state)
            instructor = self.is_instructor()
            score = state.get('score')
            approved = state.get('score_approved')
            submitted = state.get('is_submitted')
            submission_time = state.get('submission_time')

            #can a grade be entered
            due = get_extended_due_date(self)
            may_grade = (instructor or not approved) 
            if due is not None:
                may_grade = may_grade and (submitted or (due < _now())) 

            uploaded = []
            if (state.get('is_submitted')):
                for sha1, metadata in get_file_metadata(state.get("uploaded_files")).iteritems():
                    uploaded.append({
                        "sha1":      sha1, 
                        "filename":  metadata.filename,
                        "timestamp": metadata.timestamp
                    })

            annotated = []
            for sha1, metadata in get_file_metadata(state.get("annotated_files")).iteritems():
                annotated.append({
                    "sha1":      sha1, 
                    "filename":  metadata.filename,
                    "timestamp": metadata.timestamp
                })

            return {
                'module_id':       module.id,
                'username':        module.student.username,
                'fullname':        module.student.profile.name,
                'uploaded':        uploaded,
                'annotated':       annotated,
                'timestamp':       state.get("uploaded_files_last_timestamp"),
                'published':       state.get("score_published"),
                'score':           score,
                'approved':        approved,
                'needs_approval':  instructor and score is not None
                                   and not approved,
                'may_grade':       may_grade,
                'comment':         state.get("comment", ''),

                'submitted':       submitted,
                'submission_time': submission_time
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
    def get_staff_grading_data(self, request, suffix=''):
        #assert self.is_course_staff()
        if not self.is_course_staff():
            return Response(status=403)
        return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def staff_enter_grade(self, request, suffix=''):
        if not self.is_course_staff():
            return Response(status=403)
        self.enter_grade(
            request.params['module_id'],
            request.params['grade'],
            request.params.get('comment', '')
        )

        return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def staff_remove_grade(self, request, suffix=''):
        if not self.is_course_staff():
            return Response(status=403)
        self.remove_grade(request.params['module_id'])
        
        return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def student_submit(self, request, suffix=''):
        if not self.is_submitted:
            self.is_submitted = True
            submission_time = str(_now)

        return Response(status=204)

    @XBlock.handler 
    def staff_reopen_submission(self, request, suffix=''):
        #assert self.is_course_staff()
        if not self.is_course_staff():
            return Response(status=403)
        self.set_student_state(
            request.params['module_id'],
            is_submitted = False
        )        

        return Response(status=204);
        #return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def staff_reopen_all_submissions(self, request, suffix=''):
        #assert self.is_course_staff()
        if not self.is_course_staff():
            return Response(status=403)

        query = StudentModule.objects.filter(
            course_id=self.xmodule_runtime.course_id,
            module_state_key=self.location
        )

        for module in query:
            self.set_student_state(
                module.id,
                is_submitted = False
            )   

        return Response(status=204)
        #return Response(json_body=self.staff_grading_data())       

    @XBlock.handler
    def staff_remove_submission(self, request, suffix=''):
        if not self.is_course_staff():
            return Response(status=403)
        self.remove_submission(request.params['module_id'])

        return Response(status=204)
        #return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def staff_remove_all_submissions(self, request, suffix=''):
        #assert self.is_course_staff()
        if not self.is_course_staff():
            return Response(status=403)

        query = StudentModule.objects.filter(
            course_id=self.xmodule_runtime.course_id,
            module_state_key=self.location
        )

        for module in query:
            self.remove_submission(module.id)

        return Response(status=204)
        #return Response(json_body=self.staff_grading_data())

    def enter_grade(self, module_id, grade, comment=''):
        if not self.is_course_staff():
            return Response(status=403)
        self.set_student_state(
            module_id,
            score = float(grade),
            comment = comment,
            score_published = False,
            score_approved = self.is_instructor()
        )

    def remove_grade(self, module_id):
        if not self.is_course_staff():
            return Response(status=403)
        self.set_student_state(
            module_id,
            score = None,
            comment = '',
            score_published = False,
            score_approved = False
        )

    def remove_submission(self, module_id):
        state = self.get_student_state(module_id)

        self.delete_all(state.get('uploaded_files'))
        self.delete_all(state.get('annotated_files'))
        self.remove_grade(module_id)
        self.set_student_state(
            module_id,
            is_submitted = False,
            #score = None,
            #comment = '',
            #score_published = False,
            #score_approved = self.is_instructor(),
            uploaded_files = dict(),
            annotated_files = dict()
        )

    def set_student_state(self, module_id, **fields):
        """Used for staff handlers that alter the fields of a student.
        Users cannot access the fields of another user, even staff.
        In order to change a students marks are upload an annotation,
        we must do so by grabbing the student module.
        """
        assert self.is_course_staff()
        module = StudentModule.objects.get(pk=module_id)
        state = json.loads(module.state)

        for key, value in fields.iteritems():
            state[key] = value

        module.state = json.dumps(state)
        module.save()

    def past_due(self):
        """Returns True if the assignment is past due"""
        due = get_extended_due_date(self)

        if due is not None:
            return _now() > due
        else:
            return False

    def upload_allowed(self):
        """Returns True if a student is allowed to upload a file.

        In order to upload a file: the assignment must not be overdue
        and the student must not have already submitted an
        attempt.
        """
        return not self.past_due() and not self.is_submitted

    def get_module(self, module_id):
        assert self.is_course_staff()
        return StudentModule.objects.get(pk=module_id)

    def get_student_state(self, module_id):
        assert self.is_course_staff()
        module = StudentModule.objects.get(pk=module_id)
        return json.loads(module.state)

    def is_course_staff(self):
        """Returns True if requestor is part of the course staff"""
        return getattr(self.xmodule_runtime, 'user_is_staff', False)

    def is_instructor(self):
        """Returns True if the requestor is the course instructor"""
        return self.xmodule_runtime.get_user_role() == 'instructor'

    def show_staff_grading_interface(self):
        in_studio_preview = self.scope_ids.user_id is None
        return self.is_course_staff() and not in_studio_preview


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
