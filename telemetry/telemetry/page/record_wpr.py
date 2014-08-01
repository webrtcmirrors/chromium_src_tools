#!/usr/bin/env python
# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import sys
import time

from telemetry import benchmark
from telemetry.core import browser_options
from telemetry.core import discover
from telemetry.core import wpr_modes
from telemetry.page import page_measurement
from telemetry.page import page_runner
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.page import profile_creator
from telemetry.page import test_expectations
from telemetry.results import page_measurement_results


class RecorderPageTest(page_test.PageTest):  # pylint: disable=W0223
  def __init__(self, action_names):
    super(RecorderPageTest, self).__init__()
    self._action_names = action_names
    self.page_test = None

  def CanRunForPage(self, page):
    return page.url.startswith('http')

  def WillNavigateToPage(self, page, tab):
    """Override to ensure all resources are fetched from network."""
    tab.ClearCache(force=False)
    if self.page_test:
      self.page_test.options = self.options
      self.page_test.WillNavigateToPage(page, tab)

  def DidNavigateToPage(self, page, tab):
    if self.page_test:
      self.page_test.DidNavigateToPage(page, tab)

  def WillRunActions(self, page, tab):
    if self.page_test:
      self.page_test.WillRunActions(page, tab)

  def DidRunActions(self, page, tab):
    if self.page_test:
      self.page_test.DidRunActions(page, tab)

  def ValidatePage(self, page, tab, results):
    if self.page_test:
      self.page_test.ValidatePage(page, tab, results)

  def RunPage(self, page, tab, results):
    tab.WaitForDocumentReadyStateToBeComplete()

    # When recording, sleep to catch any resources that load post-onload.
    # TODO(tonyg): This should probably monitor resource timing for activity
    # and sleep until 2s since the last network event with some timeout like
    # 20s. We could wrap this up as WaitForNetworkIdle() and share with the
    # speed index metric.
    time.sleep(3)

    # When running record_wpr, results is a GTestTestResults, so we create a
    # dummy PageMeasurementResults that implements the functions we use.
    # TODO(chrishenry): Fix the need for a dummy_results object.
    dummy_results = page_measurement_results.PageMeasurementResults()

    if self.page_test:
      self._action_name_to_run = self.page_test.action_name_to_run
      self.page_test.RunPage(page, tab, dummy_results)
      return

    should_reload = False
    # Run the actions on the page for all available measurements.
    for action_name in self._action_names:
      # Skip this action if it is not defined
      if not hasattr(page, action_name):
        continue
      # Reload the page between actions to start with a clean slate.
      if should_reload:
        self.RunNavigateSteps(page, tab)
      self._action_name_to_run = action_name
      super(RecorderPageTest, self).RunPage(page, tab, dummy_results)
      should_reload = True

  def RunNavigateSteps(self, page, tab):
    if self.page_test:
      self.page_test.RunNavigateSteps(page, tab)
    else:
      super(RecorderPageTest, self).RunNavigateSteps(page, tab)


def FindAllActionNames(base_dir):
  """Returns a set of of all action names used in our measurements."""
  action_names = set()
  # Get all PageMeasurements except for ProfileCreators (see crbug.com/319573)
  for _, cls in discover.DiscoverClasses(
      base_dir, base_dir, page_measurement.PageMeasurement).items():
    if not issubclass(cls, profile_creator.ProfileCreator):
      action_name = cls().action_name_to_run
      if action_name:
        action_names.add(action_name)
  return action_names


def _MaybeGetInstanceOfClass(target, base_dir, cls):
  if isinstance(target, cls):
    return target
  classes = discover.DiscoverClasses(base_dir, base_dir, cls,
                                     index_by_class_name=True)
  return classes[target]() if target in classes else None


class WprRecorder(object):

  def __init__(self, base_dir, target, args=None):
    action_names_to_run = FindAllActionNames(base_dir)
    self._record_page_test = RecorderPageTest(action_names_to_run)
    self._options = self._CreateOptions()

    self._benchmark = _MaybeGetInstanceOfClass(target, base_dir,
                                               benchmark.Benchmark)
    if self._benchmark is not None:
      self._record_page_test.page_test = self._benchmark.test()
    self._parser = self._options.CreateParser(usage='%prog <PageSet|Benchmark>')
    self._AddCommandLineArgs()
    self._ParseArgs(args)
    self._ProcessCommandLineArgs()
    self._page_set = self._GetPageSet(base_dir, target)

  @property
  def options(self):
    return self._options

  def _CreateOptions(self):
    options = browser_options.BrowserFinderOptions()
    options.browser_options.wpr_mode = wpr_modes.WPR_RECORD
    options.browser_options.no_proxy_server = True
    return options

  def _AddCommandLineArgs(self):
    page_runner.AddCommandLineArgs(self._parser)
    if self._benchmark is not None:
      self._benchmark.AddCommandLineArgs(self._parser)
      self._benchmark.SetArgumentDefaults(self._parser)

  def _ParseArgs(self, args=None):
    args_to_parse = sys.argv[1:] if args is None else args
    self._parser.parse_args(args_to_parse)

  def _ProcessCommandLineArgs(self):
    page_runner.ProcessCommandLineArgs(self._parser, self._options)
    if self._benchmark is not None:
      self._benchmark.ProcessCommandLineArgs(self._parser, self._options)

  def _GetPageSet(self, base_dir, target):
    if self._benchmark is not None:
      return self._benchmark.CreatePageSet(self._options)
    ps = _MaybeGetInstanceOfClass(target, base_dir, page_set.PageSet)
    if ps is None:
      self._parser.print_usage()
      sys.exit(1)
    return ps

  def Record(self):
    self._page_set.wpr_archive_info.AddNewTemporaryRecording()
    self._record_page_test.CustomizeBrowserOptions(self._options)
    return page_runner.Run(self._record_page_test, self._page_set,
                           test_expectations.TestExpectations(), self._options)

  def HandleResults(self, results):
    if results.failures or results.skipped_values:
      logging.warning('Some pages failed and/or were skipped. The recording '
                      'has not been updated for these pages.')
    results.PrintSummary()
    self._page_set.wpr_archive_info.AddRecordedPages(
        results.pages_that_succeeded)


def Main(base_dir):
  quick_args = [a for a in sys.argv[1:] if not a.startswith('-')]
  if len(quick_args) != 1:
    print >> sys.stderr, 'Usage: record_wpr <PageSet|Benchmark>\n'
    sys.exit(1)
  target = quick_args.pop()
  wpr_recorder = WprRecorder(base_dir, target)
  results = wpr_recorder.Record()
  wpr_recorder.HandleResults(results)
  return min(255, len(results.failures))
