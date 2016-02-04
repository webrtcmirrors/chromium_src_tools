# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Gives a picture of the CPU activity between timestamps.

When executed as a script, takes a loading trace, and prints the activity
breakdown for the request dependencies.
"""

import collections
import logging
import operator


class ActivityLens(object):
  """Reconstructs the activity of the main renderer thread between requests."""
  def __init__(self, trace):
    """Initializes an instance of ActivityLens.

    Args:
      trace: (LoadingTrace) loading trace.
    """
    self._trace = trace
    events = trace.tracing_track.GetEvents()
    self._renderer_main_tid = self._GetRendererMainThreadId(events)

  @classmethod
  def _GetRendererMainThreadId(cls, events):
    """Returns the most active main renderer thread.

    Several renderers may be running concurrently, but we assume that only one
    of them is busy during the time covered by the loading trace.. It can be
    selected by looking at the number of trace events generated.

    Args:
      events: [tracing.Event] List of trace events.

    Returns:
      The thread ID (int) of the busiest renderer main thread.

    """
    events_count_per_tid = collections.defaultdict(int)
    main_renderer_thread_ids = set()
    for event in events:
      tracing_event = event.tracing_event
      tid = event.tracing_event['tid']
      events_count_per_tid[tid] += 1
      if (tracing_event['cat'] == '__metadata'
          and tracing_event['name'] == 'thread_name'
          and event.args['name'] == 'CrRendererMain'):
        main_renderer_thread_ids.add(tid)
    tid_events_counts = sorted(events_count_per_tid.items(),
                               key=operator.itemgetter(1), reverse=True)
    if (len(tid_events_counts) > 1
        and tid_events_counts[0][1] < 2 * tid_events_counts[1][1]):
      logging.warning(
          'Several active renderers (%d and %d with %d and %d events).'
          % (tid_events_counts[0][0], tid_events_counts[1][0],
             tid_events_counts[0][1], tid_events_counts[1][1]))
    return tid_events_counts[0][0]

  def _OverlappingEventsForTid(self, tid, start_msec, end_msec):
    events = self._trace.tracing_track.OverlappingEvents(start_msec, end_msec)
    return [e for e in events if e.tracing_event['tid'] == tid]

  @classmethod
  def _ClampedDuration(cls, event, start_msec, end_msec):
      return max(0, (min(end_msec, event.end_msec)
                     - max(start_msec, event.start_msec)))

  @classmethod
  def _ThreadBusiness(cls, events, start_msec, end_msec):
    """Amount of time a thread spent executing from the message loop."""
    busy_duration = 0
    message_loop_events = [
        e for e in events
        if (e.tracing_event['cat'] == 'toplevel'
            and e.tracing_event['name'] == 'MessageLoop::RunTask')]
    for event in message_loop_events:
      clamped_duration = cls._ClampedDuration(event, start_msec, end_msec)
      busy_duration += clamped_duration
    interval_msec = end_msec - start_msec
    assert busy_duration <= interval_msec
    return busy_duration

  @classmethod
  def _ScriptsExecuting(cls, events, start_msec, end_msec):
    """Returns the time during which scripts executed within an interval.

    Args:
      events: ([tracing.Event]) list of tracing events.
      start_msec: (float) start time in ms, inclusive.
      end_msec: (float) end time in ms, inclusive.

    Returns:
      A dict {URL (str) -> duration_msec (float)}. The dict may have a None key
      for scripts that aren't associated with a URL.
    """
    script_to_duration = collections.defaultdict(float)
    script_events = [e for e in events
                     if ('devtools.timeline' in e.tracing_event['cat']
                         and e.tracing_event['name'] in (
                             'EvaluateScript', 'FunctionCall'))]
    for event in script_events:
      clamped_duration = cls._ClampedDuration(event, start_msec, end_msec)
      script_url = event.args['data'].get('scriptName', None)
      script_to_duration[script_url] += clamped_duration
    return dict(script_to_duration)

  @classmethod
  def _Parsing(cls, events, start_msec, end_msec):
    """Returns the HTML/CSS parsing time within an interval.

    Args:
      events: ([tracing.Event]) list of events.
      start_msec: (float) start time in ms, inclusive.
      end_msec: (float) end time in ms, inclusive.

    Returns:
      A dict {URL (str) -> duration_msec (float)}. The dict may have a None key
      for tasks that aren't associated with a URL.
    """
    url_to_duration = collections.defaultdict(float)
    parsing_events = [e for e in events
                      if ('devtools.timeline' in e.tracing_event['cat']
                          and e.tracing_event['name'] in (
                              'ParseHTML', 'ParseAuthorStyleSheet'))]
    for event in parsing_events:
      tracing_event = event.tracing_event
      clamped_duration = cls._ClampedDuration(event, start_msec, end_msec)
      if tracing_event['name'] == 'ParseAuthorStyleSheet':
        url = tracing_event['args']['data']['styleSheetUrl']
      else:
        url = tracing_event['args']['beginData']['url']
      url_to_duration[url] += clamped_duration
    return dict(url_to_duration)

  def ExplainEdgeCost(self, dep):
    """For a dependency between two requests, returns the renderer activity
    breakdown.

    Args:
      dep: (Request, Request, str) As returned from
           RequestDependencyLens.GetRequestDependencies().

    Returns:
      {'edge_cost': (float) ms, 'busy': (float) ms,
       'parsing': {'url' -> time_ms}, 'script' -> {'url' -> time_ms}}
    """
    (first, second, _) = dep
    # TODO(lizeb): Refactor the edge cost computations.
    start_msec = first.start_msec
    end_msec = second.start_msec
    assert end_msec - start_msec >= 0.
    tid = self._renderer_main_tid
    events = self._OverlappingEventsForTid(tid, start_msec, end_msec)
    result = {'edge_cost': end_msec - start_msec,
              'busy': self._ThreadBusiness(events, start_msec, end_msec),
              'parsing': self._Parsing(events, start_msec, end_msec),
              'script': self._ScriptsExecuting(events, start_msec, end_msec)}
    return result


if __name__ == '__main__':
  import sys
  import json
  import loading_trace
  import request_dependencies_lens

  filename = sys.argv[1]
  json_dict = json.load(open(filename))
  loading_trace = loading_trace.LoadingTrace.FromJsonDict(json_dict)
  activity_lens = ActivityLens(loading_trace)
  dependencies_lens = request_dependencies_lens.RequestDependencyLens(
      loading_trace)
  deps = dependencies_lens.GetRequestDependencies()
  for requests_dep in deps:
    print activity_lens.ExplainEdgeCost(requests_dep)
