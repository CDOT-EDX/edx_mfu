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
import webob.exc as ExceptionResponse

from django.core.files import File
from django.core.files.storage import default_storage
from django.template import Context, Template

from functools import partial

from zipfile import ZipFile
import StringIO

from collections import namedtuple

FileMetaData = namedtuple('FileMetaData', 'filename mimetype timestamp')

log = logging.getLogger(__name__)

class FileManagementMixin(object):
	"""
	A mixin to handle file management for the SGA XBlock.
	"""
	def upload_file(self, filelist, upload):
		"""Saves a file to a list of files.
		"""
		if upload.file is none:
			raise ExceptionResponse.BadRequest(
				detail='No file in body.',
				comment='The body of the request must include a file.'
				)

		upload_key = _get_key(upload.file)

		metadata = FileMetaData(
			upload.file.name,
			mimetypes.guess_type(upload.file.name)[0],
			str( _now() )
		)

		filelist[upload_key] = metadata

		path = _file_storage_path(
			self.location.to_deprecated_string(),
			upload_key,
			upload.file.name
		)

		if not default_storage.exists(path):
			default_storage.save(path, File(upload.file))

		#Need to return the list as staff cannot directly modify student fields.
		return (upload_key, metadata)
		#return Response(json_body=self.student_state())

	def download_file(self, filelist, key):
		"""Returns a file specified by a key.

		Keyword arguments:
		filelist: a list of all files for this students submission.
		filename: the name of the zip file.
		"""
		assert filelist is not None

		if key not in filelist:
			raise ExceptionResponse.HTTPNotFound(
				detail="File not found",
				comment='No file matching hash ' + key + 'found'
				)

		#get file info
		metadata = get_file_metadata(filelist, key)
		path = _file_storage_path(
			self.location.to_deprecated_string(),
			key,
			metadata.filename
		)

		#check for file existance.
		if metadata is None:
			log.error("Problem in download_file: key exists, but metadata not found.", exc_info=True)
			raise ExceptionResponse.HTTPInternalServerError(
				detail="Error retriving file.  See log.",
				)

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
			raise ExceptionResponse.HTTPNotFound(
				detail="No files found",
				comment='There are no files of that type available.'
				)

		#buffer to create zip file in memory.
		buff = StringIO.StringIO()
		assignment_zip = ZipFile(buff, mode='w')

		for key, metadata in get_file_metadata(filelist).iteritems():
			path = _file_storage_path(
				self.location.to_deprecated_string(),
				key,
				metadata.filename
			)
			afile = default_storage.open(path)

			assignment_zip.writestr(metadata.filename, afile.read())

		assignment_zip.close()
		buff.seek(0)

		return Response(
			body =                buff.read(),
			content_type =        'application/zip',
			content_disposition = 'attachment; filename=' + filename + '.zip'
		)

	def delete_file(self, filelist, key):
		"""Removes an uploaded file from the assignment

		Keyword arguments:
		filelist: A dictionary containint file metadata.
		key:      holds the key hash of the file to be deleted.
		"""
		if key not in filelist:
			return filelist
		else:
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
		"""Removes all files in the supplied filelist

		Keyword arguments:
		filelist: A dictionary containint file metadata.
		"""
		for key in filelist.keys():
			self.delete_file(filelist, key)


def _file_storage_path(url, key, filename):
	assert url.startswith("i4x://")
	path = url[6:] + '/' + key
	path += os.path.splitext(filename)[1]
	return path

def _get_key(file):
	BLOCK_SIZE = 2**10 * 8  # 8kb
	sha1 = hashlib.sha1()
	for block in iter(partial(file.read, BLOCK_SIZE), ''):
		sha1.update(block)
	file.seek(0)

	sha1.update(str(_now()))
	return sha1.hexdigest()

def get_file_metadata(filelist, hash = None):
	"""Wraps file metadata in a FileMetaData tuple.
	Returns all files, or a single file specified by hash.

	Keyword arguments:
	filelist: a list of file metadata.
	suffix:   (optional) the hash of the desired file.
	"""
	if filelist is None: #no files => emply dict
		return dict()
	elif hash is None: #return all files.
		return {key: FileMetaData._make(metadata) 
			for (key, metadata) in filelist.iteritems()}
	else:
		if hash not in filelist: #no matching file
			return None
		else: #return one file.
			return FileMetaData._make(filelist[hash])

def _now():
	return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)