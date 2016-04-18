# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gcloud import storage
from oauth2client.client import GoogleCredentials


class GoogleStorageAccessor(object):
  """Utility class providing helpers for Google Cloud Storage.
  """
  def __init__(self, project_name, bucket_name):
    """project_name is the name of the Google Cloud project.
    bucket_name is the name of the bucket that is used for Cloud Storage calls.
    """
    self._credentials = GoogleCredentials.get_application_default()
    self._project_name = project_name
    self._bucket_name = bucket_name

  def _GetStorageClient(self):
    """Returns the storage client associated with the project"""
    return storage.Client(project = self._project_name,
                          credentials = self._credentials)

  def _GetStorageBucket(self, storage_client):
    return storage_client.get_bucket(self._bucket_name)

  def UploadFile(self, filename_src, filename_dest):
    """Uploads a file to Google Cloud Storage

    Args:
      filename_src: name of the local file
      filename_dest: name of the file in Google Cloud Storage

    Returns:
      The URL of the file in Google Cloud Storage.
    """
    client = self._GetStorageClient()
    bucket = self._GetStorageBucket(client)
    blob = bucket.blob(filename_dest)
    with open(filename_src) as file_src:
      blob.upload_from_file(file_src)
    return blob.public_url

  def UploadString(self, data_string, filename_dest):
    """Uploads a string to Google Cloud Storage

    Args:
      data_string: the contents of the file to be uploaded
      filename_dest: name of the file in Google Cloud Storage

    Returns:
      The URL of the file in Google Cloud Storage.
    """
    client = self._GetStorageClient()
    bucket = self._GetStorageBucket(client)
    blob = bucket.blob(filename_dest)
    blob.upload_from_string(data_string)
    return blob.public_url

