"""
This mixin defines handlers and fields to manage uploading assignments.
"""

import datetime
import hashlib
import json
import logging
import mimetypes
import os
import pkg_resources
import pytz

from courseware.models import StudentModule

from xblock.core import XBlock
from xblock.fields import XBlockMixin, Scope, Dict

from webob.response import Response

from django.core.files import File
# from django.core.files.storage import default_storage
# from django.template import Context, Template

log = logging.getLogger(__name__)


class FileAnnotationMixin(XBlockMixin):
    """
    Mixin for handling annotations.
    """
    annotated_files = Dict(
        display_name="Uploaded Files",
        scope=Scope.user_state,
        default=dict(),
        help="Files uploaded by the user. Tuple of filename, mimetype "
             "and timestamp"
    )

    @XBlock.handler
    def staff_upload_annotated(self, request, suffix=''):
        self.validate_staff_request(request)

        module_id = request.params['module_id']
        state = self.get_student_state(module_id)
        annotated_list = self.annotated_file_list(module_id)

        key, uploaded = self.upload_file(
            annotated_list,
            request.params['uploadedFile']
        )

        # Need to save state sepratly as user is instructor
        self.set_student_state(
            module_id,
            annotated_files=annotated_list
        )

        return Response(json_body={
            "sha1":      key,
            "filename":  uploaded.filename,
            "timestamp": uploaded.timestamp
        })

    @XBlock.handler
    def student_download_annotated(self, request, suffix=''):
        """Returns a temporary download link for an annotated file.

        Arguments:
        request: not used
        suffix:  the hash of the file.
        """
        return self.download_file(self.annotated_files, suffix)

    @XBlock.handler
    def staff_download_annotated(self, request, suffix=''):
        """Returns a temporary download link for an annotated file.

        Arguments:
        request: holds the module_id for a student module.
        suffix:  the hash of the file.
        """
        self.validate_staff_request(request)

        return self.download_file(
            self.annotated_file_list(request.params['module_id']),
            suffix
        )

    # For downloading the entire assingment for one student.
    @XBlock.handler
    def staff_download_annotated_zipped(self, request, suffix=''):
        """Returns all annotated files in a zip file.

        Arguments:
        request: holds the module_id for a student module.
        suffix:  not used.
        """
        self.validate_staff_request(request)

        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)

        return self.download_zipped(
            state['annotated_files'],
            "{}-{}-annotated".format(
                self.display_name.replace(" ","_"),
                module.student.username
            )
        )

    @XBlock.handler
    def student_download_annotated_zipped(self, request, suffix=''):
        """Returns all annotated files in a zip file.

        Arguments:
        request: not used
        suffix:  not used.
        """
        return self.download_zipped(
            self.annotated_files,
            "{}-annotated".format(self.display_name.replace(" ","_"))
        )

    @XBlock.handler
    def staff_delete_annotated(self, request, suffix=''):
        """Allows staff to remove an annotated file from a submission.
        Arguments:
        request: holds the module_id for a student module.
        suffix:  the key for the file to be deleted.
        """
        self.validate_staff_request(request)

        module_id = request.params['module_id']
        filelist = self.annotated_file_list(module_id)
        newFilelist = self.delete_file(filelist, suffix)

        self.set_student_state(
            module_id,
            annotated_files=newFilelist
        )

        return Response(json_body=self.staff_grading_data())

    def annotated_file_list(self, module_id):
        """Returns a list of annotated files for a student

        Arguments:
        module_id: A student module id.
        """
        assert self.is_course_staff()
        filelist = self.get_student_state(module_id).get('annotated_files')
        if filelist is None:
            return dict()
        else:
            return filelist


def _now():
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
