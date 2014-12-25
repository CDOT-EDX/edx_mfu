"""
This mixin defines methods for users to upload and download files,
as well as track them.
"""
import datetime
import hashlib
import json
import logging
import mimetypes
import pkg_resources
import pytz

from webob.response import Response
import webob.exc as ExceptionResponse

from django.core.files import File

# For storing files to MongoDB
import pymongo
import gridfs
from bson import ObjectId

from functools import partial

from zipfile import ZipFile
import StringIO

from collections import namedtuple

FileMetaData = namedtuple('FileMetaData', 'filename mimetype timestamp')

log = logging.getLogger(__name__)


class FileManagementMixin(object):
    """
    A mixin to handle file management for the MFU XBlock.
    """
    def upload_file(self, filelist, upload):
        """Saves a file to a list of files.
        """
        if upload.file is None:
            raise ExceptionResponse.BadRequest(
                detail='No file in body.',
                comment='The body of the request must include a file.'
            )

        fs = self.make_db_connection()

        upload_key = str(fs.put(upload.file))

        metadata = FileMetaData(
            upload.file.name,
            mimetypes.guess_type(upload.file.name)[0],
            str(_now())
        )

        filelist[upload_key] = metadata

        # Need to return key and metadata so staff can append it to list.
        return (upload_key, metadata)

    def download_file(self, filelist, key):
        """Returns a file specified by a key.

        Arguments:
        filelist: a list of all files for this students submission.
        filename: the name of the zip file.
        """
        assert filelist is not None

        if key not in filelist:
            raise ExceptionResponse.HTTPNotFound(
                detail="File not found",
                comment='No file with key {0} found'.format(key)
            )

        # get file info
        metadata = get_file_metadata(filelist, key)

        # check for file existance.
        if metadata is None:
            log.error("Problem in download_file: key exists, but "
                      "metadata not found.", exc_info=True)
            raise ExceptionResponse.HTTPInternalServerError(
                detail="Error retriving file.  See log.",
            )

        fs = self.make_db_connection()

        # set up download
        BLOCK_SIZE = 2**10 * 8  # 8kb
        foundFile = fs.get(ObjectId(key))
        app_iter = iter(partial(foundFile.read, BLOCK_SIZE), '')

        return Response(
            app_iter=app_iter,
            content_type=metadata.mimetype,
            content_disposition=
                "attachment; filename= {}".format(metadata.filename)
        )

    def download_zipped(self, filelist, filename="assignment"):
        """Return a response containg all files for this submission in
        a zip file.

        Arguments:
        filelist: a list of all files for this students submission.
        filename: the name of the zip file.
        """
        assert filelist is not None

        if (len(filelist) == 0 or filelist is None):
            raise ExceptionResponse.HTTPNotFound(
                detail="No files found",
                comment='There are no files of that type available.'
            )

        # buffer to create zip file in memory.
        buff = StringIO.StringIO()
        assignment_zip = ZipFile(buff, mode='w')

        fs = self.make_db_connection()

        # pack assignment submission into a zip file.
        for key, metadata in get_file_metadata(filelist).iteritems():
            afile = fs.get(ObjectId(key))
            assignment_zip.writestr(metadata.filename, afile.read())
            afile.close()

        assignment_zip.close()
        buff.seek(0)

        return Response(
            body=buff.read(),
            content_type='application/zip',
            content_disposition=
                'attachment; filename={}.zip'.format(filename)
        )

    def delete_file(self, filelist, key):
        """Removes an uploaded file from the assignment

        Arguments:
        filelist: A dictionary containint file metadata.
        key:      holds the key hash of the file to be deleted.
        """
        if key not in filelist:
            return filelist
        else:
            metadata = get_file_metadata(filelist, ObjectId(key))

        fs = self.make_db_connection()

        fs.delete(ObjectId(key))
        del filelist[key]

        return filelist

    def delete_all(self, filelist):
        """Removes all files in the supplied filelist

        Arguments:
        filelist: A dictionary containint file metadata.
        """
        if filelist is None:
            return

        for key in filelist.keys():
            self.delete_file(filelist, ObjectId(key))

    def make_db_connection(self):
        """Opens a connection to MongoDB for this assignments submissions.
        """
        _db = pymongo.database.Database(
            pymongo.MongoClient(
                host='localhost',
                port=27017,
                document_class=dict,
            ),
            "edx_mfu"
        )

        return gridfs.GridFS(
            _db,
            "fs.{0}".format(self.location.to_deprecated_string())
        )


def get_file_metadata(filelist, hash=None):
    """Wraps file metadata in a FileMetaData tuple.
    Returns all files, or a single file specified by hash.

    Arguments:
    filelist: a list of file metadata.
    suffix:   (optional) the hash of the desired file.
    """
    if filelist is None:  # no files => emply dict
        return dict()
    elif hash is None:  # return all files.
        return {key: FileMetaData._make(metadata)
                for (key, metadata) in filelist.iteritems()}
    else:
        if hash not in filelist:  # no matching file
            return None
        else:  # return one file.
            return FileMetaData._make(filelist[hash])


def _now():
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
