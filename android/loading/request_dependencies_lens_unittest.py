# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import devtools_monitor
from loading_trace import LoadingTrace
from request_dependencies_lens import RequestDependencyLens
from request_track import (Request, TimingFromDict)
from page_track import PageTrack


class FakeTrack(devtools_monitor.Track):
  def __init__(self, events):
    super(FakeTrack, self).__init__(None)
    self._events = events

  def GetEvents(self):
    return self._events


class FakeRequestTrack(devtools_monitor.Track):
  def __init__(self, events):
    super(FakeRequestTrack, self).__init__(None)
    self._events = [self._RewriteEvent(e) for e in events]

  def GetEvents(self):
    return self._events

  def _RewriteEvent(self, event):
    # This modifies the instance used across tests, so this method
    # must be idempotent.
    event.timing = event.timing._replace(request_time=event.timestamp)
    return event


class RequestDependencyLensTestCase(unittest.TestCase):
  _REDIRECT_REQUEST = Request.FromJsonDict(
      {'url': 'http://bla.com', 'request_id': '1234.1.redirect',
       'initiator': {'type': 'other'},
       'timestamp': 1, 'timing': TimingFromDict({})})
  _REQUEST = Request.FromJsonDict({'url': 'http://bla.com',
                                   'request_id': '1234.1',
                                   'frame_id': '123.1',
                                   'initiator': {'type': 'other'},
                                   'timestamp': 2,
                                   'timing': TimingFromDict({})})
  _JS_REQUEST = Request.FromJsonDict({'url': 'http://bla.com/nyancat.js',
                                      'request_id': '1234.12',
                                      'frame_id': '123.1',
                                      'initiator': {'type': 'parser',
                                                    'url': 'http://bla.com'},
                                      'timestamp': 3,
                                      'timing': TimingFromDict({})})
  _JS_REQUEST_OTHER_FRAME = Request.FromJsonDict(
      {'url': 'http://bla.com/nyancat.js',
       'request_id': '1234.42',
       'frame_id': '123.13',
       'initiator': {'type': 'parser',
                     'url': 'http://bla.com'},
       'timestamp': 4, 'timing': TimingFromDict({})})
  _JS_REQUEST_UNRELATED_FRAME = Request.FromJsonDict(
      {'url': 'http://bla.com/nyancat.js',
       'request_id': '1234.42',
       'frame_id': '123.99',
       'initiator': {'type': 'parser',
                     'url': 'http://bla.com'},
       'timestamp': 5, 'timing': TimingFromDict({})})
  _JS_REQUEST_2 = Request.FromJsonDict(
      {'url': 'http://bla.com/cat.js', 'request_id': '1234.13',
       'frame_id': '123.1',
       'initiator': {'type': 'script',
                     'stackTrace': [{'url': 'unknown'},
                                    {'url': 'http://bla.com/nyancat.js'}]},
       'timestamp': 10, 'timing': TimingFromDict({})})
  _PAGE_TRACK = FakeTrack(
      [{'method': 'Page.frameAttached',
        'frame_id': '123.13', 'parent_frame_id': '123.1'}])

  def testRedirectDependency(self):
    request_track = FakeRequestTrack([self._REDIRECT_REQUEST, self._REQUEST])
    loading_trace = LoadingTrace(None, None, PageTrack(None),
                                 request_track, None)
    request_dependencies_lens = RequestDependencyLens(loading_trace)
    deps = request_dependencies_lens.GetRequestDependencies()
    self.assertEquals(1, len(deps))
    (first, second, reason) = deps[0]
    self.assertEquals('redirect', reason)
    self.assertEquals(self._REDIRECT_REQUEST.request_id, first.request_id)
    self.assertEquals(self._REQUEST.request_id, second.request_id)

  def testScriptDependency(self):
    request_track = FakeRequestTrack([self._JS_REQUEST, self._JS_REQUEST_2])
    loading_trace = LoadingTrace(None, None, PageTrack(None),
                                 request_track, None)
    request_dependencies_lens = RequestDependencyLens(loading_trace)
    deps = request_dependencies_lens.GetRequestDependencies()
    self.assertEquals(1, len(deps))
    self._AssertDependencyIs(
        deps[0],
        self._JS_REQUEST.request_id, self._JS_REQUEST_2.request_id, 'script')

  def testParserDependency(self):
    request_track = FakeRequestTrack([self._REQUEST, self._JS_REQUEST])
    loading_trace = LoadingTrace(None, None, PageTrack(None),
                                 request_track, None)
    request_dependencies_lens = RequestDependencyLens(loading_trace)
    deps = request_dependencies_lens.GetRequestDependencies()
    self.assertEquals(1, len(deps))
    self._AssertDependencyIs(
        deps[0],
        self._REQUEST.request_id, self._JS_REQUEST.request_id, 'parser')

  def testSeveralDependencies(self):
    request_track = FakeRequestTrack(
        [self._REDIRECT_REQUEST, self._REQUEST, self._JS_REQUEST,
         self._JS_REQUEST_2])
    loading_trace = LoadingTrace(None, None, PageTrack(None),
                                 request_track, None)
    request_dependencies_lens = RequestDependencyLens(loading_trace)
    deps = request_dependencies_lens.GetRequestDependencies()
    self.assertEquals(3, len(deps))
    self._AssertDependencyIs(
        deps[0], self._REDIRECT_REQUEST.request_id, self._REQUEST.request_id,
        'redirect')
    self._AssertDependencyIs(
        deps[1],
        self._REQUEST.request_id, self._JS_REQUEST.request_id, 'parser')
    self._AssertDependencyIs(
        deps[2],
        self._JS_REQUEST.request_id, self._JS_REQUEST_2.request_id, 'script')

  def testDependencyDifferentFrame(self):
    """Checks that a more recent request from another frame is ignored."""
    request_track = FakeRequestTrack(
        [self._JS_REQUEST, self._JS_REQUEST_OTHER_FRAME, self._JS_REQUEST_2])
    loading_trace = LoadingTrace(None, None, PageTrack(None),
                                 request_track, None)
    request_dependencies_lens = RequestDependencyLens(loading_trace)
    deps = request_dependencies_lens.GetRequestDependencies()
    self.assertEquals(1, len(deps))
    self._AssertDependencyIs(
        deps[0],
        self._JS_REQUEST.request_id, self._JS_REQUEST_2.request_id, 'script')

  def testDependencySameParentFrame(self):
    """Checks that a more recent request from an unrelated frame is ignored
    if there is one from a related frame."""
    request_track = FakeRequestTrack(
        [self._JS_REQUEST_OTHER_FRAME, self._JS_REQUEST_UNRELATED_FRAME,
         self._JS_REQUEST_2])
    loading_trace = LoadingTrace(None, None, self._PAGE_TRACK,
                                 request_track, None)
    request_dependencies_lens = RequestDependencyLens(loading_trace)
    deps = request_dependencies_lens.GetRequestDependencies()
    self.assertEquals(1, len(deps))
    self._AssertDependencyIs(
        deps[0],
        self._JS_REQUEST_OTHER_FRAME.request_id,
        self._JS_REQUEST_2.request_id, 'script')

  def _AssertDependencyIs(
      self, dep, first_request_id, second_request_id, reason):
    (first, second, dependency_reason) = dep
    self.assertEquals(reason, dependency_reason)
    self.assertEquals(first_request_id, first.request_id)
    self.assertEquals(second_request_id, second.request_id)


if __name__ == '__main__':
  unittest.main()
