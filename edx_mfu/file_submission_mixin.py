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

log = logging.getLogger(__name__)

class FileSubmissionMixin(XBlockMixin):
    """
    Mixin for handling file submissions.
    """
    uploaded_files = Dict(
        display_name="Uploaded Files",
        scope=Scope.user_state,
        default=dict(),
        help="Files uploaded by the user. Tuple of filename, "
             "mimetype and timestamp"
    )

    @XBlock.handler
    def student_upload_file(self, request, suffix=''):
        """Allows a student to upload a file for submission.

        Arguments:
        request: holds the file to be added to the submission.
        suffix:  not used.
        """

        key, uploaded = self.upload_file(
            self.uploaded_files,
            request.params['uploadedFile']
        )

        return Response(json_body={
            "sha1":      key,
            "filename":  uploaded.filename,
            "timestamp": uploaded.timestamp
        })

    @XBlock.handler
    def student_download_file(self, request, suffix=''):
        """Returns a temporary download link for a file.

        Arguments:
        request: not used
        suffix:  the hash of the file.
        """
        return self.download_file(self.uploaded_files, suffix)

    @XBlock.handler
    def staff_download_file(self, request, suffix=''):
        """Returns a temporary download link for a file.

        Arguments:
        request: holds the module_id for a student module.
        suffix:  the hash of the file.
        """
        self.validate_staff_request(request)

        return self.download_file(
            self.uploaded_file_list(request.params['module_id']),
            suffix
        )

    @XBlock.handler
    def staff_download_zipped(self, request, suffix=''):
        """Returns all uploaded files in a zip file.

        Arguments:
        request: holds the module_id for a student module.
        suffix:  not used.
        """
        self.validate_staff_request(request)

        module_id = request.params['module_id']
        module = self.get_module(module_id)
        return self.download_zipped(
            self.uploaded_file_list(module_id),
            "{}-{}".format(
                self.display_name.replace(" ","_"),
                module.student.username
            )
        )

    @XBlock.handler
    def student_download_zipped(self, request, suffix=''):
        """Returns all uploaded files in a zip file.

        Arguments:
        request: not used.
        suffix:  not used.
        """
        return self.download_zipped(
            self.uploaded_files,
            "{}".format(self.display_name.replace(" ","_"))
        )

    @XBlock.handler
    def student_delete_file(self, request, suffix=''):
        """Removes an uploaded file from the assignemnt

        Arguments:
        request: not used.
        suffix:  holds the key hash of the file to be deleted.
        """
        assert self.upload_allowed()
        self.delete_file(self.uploaded_files, suffix)
        return Response(status=204)

    @XBlock.handler
    def staff_delete_file(self, request, suffix=''):
        """Removes an uploaded file from the assignemnt

        Arguments:
        request: holds module_id.
        suffix:  holds the key hash of the file to be deleted.
        """
        self.validate_staff_request(request)

        module_id = request.params['module_id']
        uploaded = self.get_student_state(module_id).get('uploaded_files')

        newFilelist = self.delete_file(uploaded, suffix)
        self.set_student_state(
            module_id,
            uploaded_files=newFilelist
        )

        return Response(status=204)

    def uploaded_file_list(self, module_id):
        """Returns a list of files uploaded by a student.

        Arguments:
        module_id: A student module id.
        """
        assert self.is_course_staff()
        return self.get_student_state(module_id)['uploaded_files']


def _now():
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
