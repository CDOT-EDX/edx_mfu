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

from xblock.core import XBlock
from xblock.fields import XBlockMixin

from webob.response import Response

from django.core.files import File
from django.core.files.storage import default_storage
from django.template import Context, Template

from functools import partial

from zipfile import ZipFile
import StringIO

class FileSubmissionMixin(XBlockMixin):
	"""
	"""

    uploaded_files = Dict(
        display_name="Uploaded Files",
        scope=Scope.user_state,
        default=dict(),
        help="Files uploaded by the user. Tuple of filename, mimetype and timestamp"
    )	

    @XBlock.handler
    def student_upload_file(self, request, suffix=''):
        assert self.upload_allowed()
        upload = request.params['assignment']

        return self.upload_file(self.uploaded_files, upload)
        
    @XBlock.handler
    def student_download_file(self, request, suffix=''):
        return self.download_file(self.uploaded_files, suffix)

    @XBlock.handler
    def staff_download_file(self, request, suffix=''):
        assert self.is_course_staff()
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)

        return self.download_file(state['uploaded_files'], suffix)
    
    #For downloading the entire assingment for one student.
    @XBlock.handler
    def staff_download_zipped(self, request, suffix=''):
        assert self.is_course_staff()
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)

        #TODO: assignment name with student, course and assignemnt name.
        return self.download_zipped(self.uploaded_files, 'assignment')

    @XBlock.handler
    def student_download_zipped(self, request, suffix=''):
        #TODO: assignment name with course and assignemnt name.
        return self.download_zipped(self.uploaded_files, 'assignment')

    @XBlock.handler
    def student_delete_file(self, request, suffix=''):
        """Removes an uploaded file from the assignemtn

        Keyword arguments:
        request: not used.
        suffix:  holds the sha1 hash of the file to be deleted.
        """
        assert self.upload_allowed()
        self.delete_file(self.uploaded_files, suffix)
        return Response(status = 204)

    @XBlock.handler
    def staff_delete_file(self, request, suffix=''):
        module_id = request.params['module_id']
        uploaded = self.get_student_state(module_id).get('uploaded_files')

        newFilelist = self.delete_file(uploaded, suffix)
        self.set_student_state(
            module_id, 
            uploaded_files = newFilelist
        )

        return Response(status=204)

    @XBlock.handler
    def student_submit(self, request, suffix=''):
        if not self.is_submitted:
            self.is_submitted = True
            submission_time = str(_now)

        return Response(status=204)

    @XBlock.handler 
    def staff_reopen_submission(self, request, suffix=''):
        assert self.is_course_staff()
        self.set_student_state(
            request.params['module_id'],
            is_submitted = False
        )        

        return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def staff_reopen_all_submissions(self, request, suffix=''):
        assert self.is_course_staff()
        query = StudentModule.objects.filter(
            course_id=self.xmodule_runtime.course_id,
            module_state_key=self.location
        )

        for module in query:
            self.set_student_state(
                module.id,
                is_submitted = False
            )   

        return Response(json_body=self.staff_grading_data())       

    @XBlock.handler
    def staff_remove_submission(self, request, suffix=''):
        self.remove_submission(request.params['module_id'])

        return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def staff_remove_all_submissions(self, request, suffix=''):
        assert self.is_course_staff()
        query = StudentModule.objects.filter(
            course_id=self.xmodule_runtime.course_id,
            module_state_key=self.location
        )

        for module in query:
            self.remove_submission(module.id)

        return Response(json_body=self.staff_grading_data())
