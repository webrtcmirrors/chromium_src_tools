#! /usr/bin/python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An integration test for tracing.

This is not run as part of unittests and is executed directly. In normal
operation it can be run with no arguments (or perhaps --no_sandbox depending on
how you have chrome set up). When debugging or adding tests, setting
--failed_trace_dir could be useful.

Spawns a local http server to serve web pages. The trace generated by each
file in tests/*.html will be compared with the corresponding results/*.result.

By default this will use a release version of chrome built in this same
code tree (out/Release/chrome), see --local_binary to override.
"""

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from device_setup import DeviceConnection
import loading_trace
import options
import trace_recorder

OPTIONS = options.OPTIONS
WEBSERVER = os.path.join(os.path.dirname(__file__), 'test_server.py')
TESTDIR = os.path.join(os.path.dirname(__file__), 'tests')
RESULTDIR = os.path.join(os.path.dirname(__file__), 'results')


@contextlib.contextmanager
def TemporaryDirectory():
  """Returns a freshly-created directory that gets automatically deleted after
  usage.
  """
  name = tempfile.mkdtemp()
  try:
    yield name
  finally:
    shutil.rmtree(name)


class WebServer(object):
  """Wrap the webserver."""
  def __init__(self, source_dir, communication_dir):
    """Initialize the server but does not start it.

    Args:
      source_dir: the directory where source data (html, js, etc) will be found.
      communication_dir: a directory to use for IPC (eg, discovering the
        port, which is dynamically allocated). This should probably be a
        temporary directory.
    """
    self._source_dir = source_dir
    self._communication_dir = communication_dir
    self._fifo = None
    self._server_process = None
    self._port = None

  @classmethod
  @contextlib.contextmanager
  def Context(cls, *args, **kwargs):
    """Creates a webserver as a context manager.

    Args:
      As in __init__.

    Returns:
      A context manager for an instance of a WebServer.
    """
    try:
      server = cls(*args, **kwargs)
      server.Start()
      yield server
    finally:
      server.Stop()

  def Start(self):
    """Start the server by spawning a process."""
    fifo_name = os.path.join(self._communication_dir, 'from_server')
    os.mkfifo(fifo_name)
    server_out = None if OPTIONS.local_noisy else file('/dev/null', 'w')
    self._server_process = subprocess.Popen(
        [WEBSERVER,
         '--source_dir=%s' % self._source_dir,
         '--fifo=%s' % fifo_name],
        shell=False, stdout=server_out, stderr=server_out)
    fifo = file(fifo_name)
    # TODO(mattcary): timeout?
    self._port = int(fifo.readline())
    fifo.close()

  def Stop(self):
    """Stops the server, waiting for it to complete.

    Returns:
      True if the server stopped correctly.
    """
    if self._server_process is None:
      return False
    self._server_process.kill()
    # TODO(mattcary): timeout & error?
    self._server_process.wait()
    return True

  def Address(self):
    """Returns a host:port string suitable for an http request."""
    assert self._port is not None, \
        "No port exists until the server is started."
    return 'localhost:%s' % self._port


class InitiatorSequence(object):
  """The interesting parts of the initiator dependancies that are tested."""
  def __init__(self, trace):
    """Create.

    Args:
      trace: a LoadingTrace.
    """
    self._seq = []
    # ReadFromFile will initialize without a trace.
    if trace is None:
      return
    for rq in trace.request_track.GetEvents():
      if rq.initiator['type'] in ('parser', 'script'):
        stack = 'no stack'
        if 'stack' in rq.initiator:
          stack = '/'.join(
              ['%s:%s' % (self._ShortUrl(frame['url']), frame['lineNumber'])
               for frame in rq.initiator['stack']['callFrames']])
        self._seq.append('%s (%s) %s' % (
            rq.initiator['type'],
            stack,
            self._ShortUrl(rq.url)))
    self._seq.sort()

  @classmethod
  def ReadFromFile(cls, input_file):
    """Read a file from DumpToFile.

    Args:
      input_file: a file-like object.

    Returns:
      An InitiatorSequence instance.
    """
    seq = cls(None)
    seq._seq = sorted([l.strip() for l in input_file.readlines() if l])
    return seq

  def DumpToFile(self, output):
    """Write to a file.

    Args:
      output: a writeable file-like object.
    """
    output.write('\n'.join(self._seq) + '\n')

  def __eq__(self, other):
    if other is None:
      return False
    assert type(other) is InitiatorSequence
    if len(self._seq) != len(other._seq):
      return False
    for a, b in zip(self._seq, other._seq):
      if a != b:
        return False
    return True

  def _ShortUrl(self, url):
    short = urlparse.urlparse(url).path
    while short.startswith('/'):
      short = short[1:]
    if len(short) > 40:
      short = '...'.join((short[:20], short[-10:]))
    return short


def RunTest(webserver, connection, test_page, expected):
  """Run an webserver test.

  The expected result can be None, in which case --failed_trace_dir can be set
  to output the observed trace.

  Args:
    webserver [WebServer]: the webserver to use for the test. It must be
      started.
    connection [DevToolsConnection]: the connection to trace against.
    test_page: the name of the page to load.
    expected [InitiatorSequence]: expected initiator sequence.

  Returns:
    True if the test passed and false otherwise. Status is printed to stdout.
  """
  url = 'http://%s/%s' % (webserver.Address(), test_page)
  sys.stdout.write('Testing %s...' % url)
  observed_seq = InitiatorSequence(trace_recorder.MonitorUrl(
      connection, url, clear_cache=True))
  if observed_seq == expected:
    sys.stdout.write(' ok\n')
    return True
  else:
    sys.stdout.write(' FAILED!\n')
    if OPTIONS.failed_trace_dir:
      outname = os.path.join(OPTIONS.failed_trace_dir,
                             test_page + '.observed_result')
      with file(outname, 'w') as output:
        observed_seq.DumpToFile(output)
      sys.stdout.write('Wrote observed result to %s\n' % outname)
  return False


def RunAllTests():
  """Run all tests in TESTDIR.

  All tests must have a corresponding result in RESULTDIR unless
  --failed_trace_dir is set.
  """
  with TemporaryDirectory() as temp_dir, \
       WebServer.Context(TESTDIR, temp_dir) as webserver, \
       DeviceConnection(None) as connection:
    failure = False
    for test in sorted(os.listdir(TESTDIR)):
      if test.endswith('.html'):
        result = os.path.join(RESULTDIR, test[:test.rfind('.')] + '.result')
        assert OPTIONS.failed_trace_dir or os.path.exists(result), \
            'No result found for test'
        expected = None
        if os.path.exists(result):
          with file(result) as result_file:
            expected = InitiatorSequence.ReadFromFile(result_file)
        if not RunTest(webserver, connection, test, expected):
          failure = True
  if failure:
    print 'FAILED!'
  else:
    print 'all tests passed'


if __name__ == '__main__':
  OPTIONS.ParseArgs(sys.argv[1:],
                    description='Run webserver integration test',
                    extra=[('--failed_trace_dir', ''),
                           ('--noisy', False)])
  RunAllTests()
