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

class FileSubmissionMixin(XBlockMixin):
	"""
	Mixin for handling file submissions.
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

		return self.upload_file(
			self.uploaded_files, 
			request.params['assignment']
		)
		
	@XBlock.handler
	def student_download_file(self, request, suffix=''):
		return self.download_file(self.uploaded_files, suffix)

	@XBlock.handler
	def staff_download_file(self, request, suffix=''):
		assert self.is_course_staff()
		return self.download_file(
			self.uploaded_file_list(request.params['moudule_id']),
			suffix
		 )
	
	#For downloading the entire assingment for one student.
	@XBlock.handler
	def staff_download_zipped(self, request, suffix=''):
		module = self.get_module(request.params['module_id'])
		return self.download_zipped(
			self.uploaded_file_list(request.params['moudule_id']), 
			self.display_name + "-" + module.student.username + ".zip"
		)

	@XBlock.handler
	def student_download_zipped(self, request, suffix=''):
		module = self.get_module(request.params['module_id'])
		return self.download_zipped(
			self.uploaded_files, 
			self.display_name + "-" + module.student.username + ".zip"
		)

	@XBlock.handler
	def student_delete_file(self, request, suffix=''):
		"""Removes an uploaded file from the assignemtn

		Keyword arguments:
		request: not used.
		suffix:  holds the key hash of the file to be deleted.
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

	def uploaded_file_list(self, module_id):
		assert self.is_course_staff()
		return get_student_state(module_id)['uploaded_files']

def _now():
	return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)