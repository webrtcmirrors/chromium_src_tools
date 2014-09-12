# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging as real_logging


class Device(object):
  """ A base class of devices.
  A device instance contains all the necessary information for constructing
  a platform backend object for remote platforms.

  Attributes:
    name: A device name string in human-understandable term.
    device_id: A unique id of the device. Subclass of device must specify this
      id properly so that device objects to a same actual device must have same
      device_id.
    """

  def __init__(self, name, device_id):
    self._name = name
    self._device_id = device_id

  @property
  def name(self):
    return self._name

  @property
  def device_id(self):
    return self._device_id

  @classmethod
  def GetAllConnectedDevices(cls, logging=real_logging):
    raise NotImplementedError()
