"""
This mixin defines methods for users to upload and download files,
as well as track them.
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

from collections import namedtuple

FileMetaData = namedtuple('FileMetaData', 'filename mimetype timestamp')

class FileManagementMixin(XBlockMixin):
	"""
	A mixin to handle file management for the SGA XBlock.
	"""
	def upload_file(self, filelist, upload):
		upload_sha1 = _get_sha1(upload)

		metadata = FileMetaData(
			upload.file.name,
			mimetypes.guess_type(upload)[0],
			str( _now() )
		)

		filelist[upload_sha1] = metadata

		path = _file_storage_path(
			self.location.to_deprecated_string(),
			upload_sha1,
			upload.file.name
		)

		if not default_storage.exists(path):
			default_storage.save(path, File(upload.file))
		return Response(json_body=self.student_state())

	def download_file(self, filelist, sha1):
		"""Returns a file s
		"""
		assert filelist is not None

		if sha1 not in filelist:
			log.error("File download failure: No matching file belongs to this student.", exc_info=True)
			raise

		#get file info
		metadata = get_file_metadata(filelist, sha1)
		path = _file_storage_path(
			self.location.to_deprecated_string(),
			sha1,
			metadata.filename
		)

		if metadata is None:
			log.error("Attempt to download non-existant file at " + path)
			return Response(status = 404)

		#set up download
		BLOCK_SIZE = 2**10 * 8  # 8kb
		foundFile = default_storage.open(path)
		app_iter = iter(partial(foundFile.read, BLOCK_SIZE), '')

		return Response(
			app_iter =             app_iter,
			content_type =         metadata.mimetype,
			content_disposition = "attachment; filename=" + metadata.filename
		)

	#TODO: Filename based on requestor and submittor
	def download_zipped(self, filelist, filename="assignment"):
		"""Return a response containg all files for this submission in
		a zip file.

		Keyword arguments:
		filelist: a list of all files for this students submission.
		filename: the name of the zip file.
		"""
		assert filelist is not None 

		if (len(filelist) == 0 or filelist is None):
			return Response(status = 404)

		buff = StringIO.StringIO()
		assignment_zip = ZipFile(buff, mode='w')

		for sha1, metadata in get_file_metadata(filelist).iteritems():
			path = _file_storage_path(
				self.location.to_deprecated_string(),
				sha1,
				metadata.filename
			)
			afile = default_storage.open(path)

			assignment_zip.writestr(metadata.filename, afile.read())

		assignment_zip.close()
		buff.seek(0)

		return Response(
			body =                buff.read(),
			content_type =        'application/zip',
			content_disposition = 'attachment; filename=assignment' + '.zip'
		)

	def delete_file(self, filelist, key):
		"""Removes an uploaded file from the assignment

		Keyword arguments:
		request: not used.
		suffix:  holds the sha1 hash of the file to be deleted.
		"""
		assert self.upload_allowed()

		if suffix in filelist:
			metadata = get_file_metadata(filelist, key)

		path = _file_storage_path(
			self.location.to_deprecated_string(),
			key,
			metadata.filename
		)

		default_storage.delete(path)
		del filelist[key]

		return filelist

	def delete_all(self, filelist):
		assert self.upload_allowed();

		for sha1 in filelist.keys():
			self.delete(filelist, sha1)


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

def get_file_metadata(filelist, hash = None):
    if hash is None:
        return {sha1: FileMetaData._make(metadata) 
            for (sha1, metadata) in filelist.iteritems()}
        #ret = {}
        #for sha1, metadata in filelist.iteritems():
        #    ret[sha1] = FileMetaData.__make(make)
    else:
        if hash not in filelist:
            return None
        else:
            return FileMetaData._make(filelist[hash])