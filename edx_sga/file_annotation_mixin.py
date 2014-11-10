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
from xblock.fields import XBlockMixin, Dict

from webob.response import Response

from django.core.files import File
from django.core.files.storage import default_storage
from django.template import Context, Template

class FileAnnotationMixin(XBlockMixin):
	"""
    Mixin for handling annotations.
	"""
    annotated_files = Dict(
        display_name="Uploaded Files",
        scope=Scope.user_state,
        default=dict(),
        help="Files uploaded by the user. Tuple of filename, mimetype and timestamp"
    )	

    @XBlock.handler
    def staff_upload_annotation(self, request, suffix=''):
        self.get_student_state(request.params['module_id'])
        upload = request.params['assignment']

        return self.upload_file(
            self.get_student_state(request.params['module_id'], 
            request.params['assignment']
        )
        
    @XBlock.handler
    def student_download_annotation(self, request, suffix=''):
        return self.download_file(self.annotated_files, suffix)

    @XBlock.handler
    def staff_download_annotation(self, request, suffix=''):
        return self.download_file(
            self.get_student_state(request.params['module_id'], 
            suffix
        )
    
    #For downloading the entire assingment for one student.
    @XBlock.handler
    def staff_download_annotation_zipped(self, request, suffix=''):
        assert self.is_course_staff()
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)

        #TODO: assignment name with student, course and assignemnt name.
        #return self.download_zipped(self.annotated_files, 'assignment')
        return self.download_zipped(
            state['annotated_files'], 
            display_name + "-" + username + "annotated.zip";
        )

    @XBlock.handler
    def student_download_annotation_zipped(self, request, suffix=''):
        #TODO: assignment name with course and assignemnt name.
        #return self.download_zipped(self.annotated_files, 'assignment')
        return self.download_zipped(
            self.annotated_files, 
            display_name + "-" + username + "annotated.zip";
        )
    @XBlock.handler
    def staff_delete_annotation(self, request, suffix=''):
        module_id = request.params['module_id']
        uploaded = self.get_student_state(module_id)
        newFilelist = self.delete_file(uploaded, suffix)
        self.set_student_state(
            module_id, 
            annotated_files = newFilelist
        )

        return Response(status=204)

    def annotated_file_list(self, module_id):
        return get_student_state(module_id)['annotated_files']

def _now():
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)