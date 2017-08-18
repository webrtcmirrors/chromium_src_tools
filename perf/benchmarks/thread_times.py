# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from core import perf_benchmark

from benchmarks import silk_flags
from measurements import thread_times
import page_sets
from telemetry import benchmark
from telemetry import story


class _ThreadTimes(perf_benchmark.PerfBenchmark):

  @classmethod
  def AddBenchmarkCommandLineArgs(cls, parser):
    parser.add_option('--report-silk-details', action='store_true',
                      help='Report details relevant to silk.')

  @classmethod
  def Name(cls):
    return 'thread_times'

  @classmethod
  def ValueCanBeAddedPredicate(cls, value, _):
    # Default to only reporting per-frame metrics.
    return 'per_second' not in value.name

  def SetExtraBrowserOptions(self, options):
    silk_flags.CustomizeBrowserOptionsForThreadTimes(options)

  def CreatePageTest(self, options):
    return thread_times.ThreadTimes(options.report_silk_details)


@benchmark.Owner(emails=['vmiura@chromium.org'])
class ThreadTimesKeySilkCases(_ThreadTimes):
  """Measures timeline metrics while performing smoothness action on key silk
  cases."""
  page_set = page_sets.KeySilkCasesPageSet

  @classmethod
  def Name(cls):
    return 'thread_times.key_silk_cases'

  def GetExpectations(self):
    class StoryExpectations(story.expectations.StoryExpectations):
      def SetExpectations(self):
        self.PermanentlyDisableBenchmark(
            [story.expectations.ALL_DESKTOP], 'Mobile Benchmark')
        self.DisableStory('https://polymer-topeka.appspot.com/',
                          [story.expectations.ALL], 'crbug.com/507865')
        self.DisableStory('http://plus.google.com/app/basic/stream',
                          [story.expectations.ALL], 'crbug.com/338838')
        self.DisableStory('inbox_app.html?slide_drawer',
                          [story.expectations.ALL], 'crbug.com/446332')
    return StoryExpectations()


class ThreadTimesKeyHitTestCases(_ThreadTimes):
  """Measure timeline metrics while performing smoothness action on key hit
  testing cases."""
  page_set = page_sets.KeyHitTestCasesPageSet

  @classmethod
  def Name(cls):
    return 'thread_times.key_hit_test_cases'

  def GetExpectations(self):
    class StoryExpectations(story.expectations.StoryExpectations):
      def SetExpectations(self):
        self.PermanentlyDisableBenchmark(
            [story.expectations.ALL_MAC, story.expectations.ALL_WIN],
            'Android and Linux Benchmark')
        self.PermanentlyDisableBenchmark(
            [story.expectations.ALL],
            'Disabled on all platforms due to use of deprecated web platform '
            'features. Crbug.com/750876.')
    return StoryExpectations()


@benchmark.Owner(emails=['vmiura@chromium.org'])
class ThreadTimesKeyMobileSitesSmooth(_ThreadTimes):
  """Measures timeline metrics while performing smoothness action on
  key mobile sites labeled with fast-path tag.
  http://www.chromium.org/developers/design-documents/rendering-benchmarks"""
  page_set = page_sets.KeyMobileSitesSmoothPageSet
  options = {'story_tag_filter': 'fastpath'}

  @classmethod
  def Name(cls):
    return 'thread_times.key_mobile_sites_smooth'

  def GetExpectations(self):
    class StoryExpectations(story.expectations.StoryExpectations):
      def SetExpectations(self):
        self.PermanentlyDisableBenchmark(
            [story.expectations.ALL_DESKTOP], 'Mobile Benchmark')
        # TODO(rnephew): Uncomment when these stories is rerecorded.
        # self.DisableStory(
        #     'http://forecast.io', [story.expectations.ALL],
        #     'crbug.com/249736')
        # self.DisableStory(
        #    'Twitter', [story.expectations.ALL],
        #    'Forbidden (Rate Limit Exceeded)')
        # self.DisableStory('ESPN', [story.expectations.ALL],
        #                   'crbug.com/249722')
    return StoryExpectations()


@benchmark.Owner(emails=['vmiura@chromium.org'])
class ThreadTimesSimpleMobileSites(_ThreadTimes):
  """Measures timeline metric using smoothness action on simple mobile sites
  http://www.chromium.org/developers/design-documents/rendering-benchmarks"""
  page_set = page_sets.SimpleMobileSitesPageSet

  @classmethod
  def Name(cls):
    return 'thread_times.simple_mobile_sites'

  def GetExpectations(self):
    class StoryExpectations(story.expectations.StoryExpectations):
      def SetExpectations(self):
        self.PermanentlyDisableBenchmark(
            [story.expectations.ALL_DESKTOP], 'Mobile Benchmark')
        self.DisableStory('https://www.flickr.com/', [story.expectations.ALL],
                          'crbug.com/752228')
    return StoryExpectations()


@benchmark.Owner(emails=['vmiura@chromium.org'])
class ThreadTimesCompositorCases(_ThreadTimes):
  """Measures timeline metrics while performing smoothness action on
  tough compositor cases, using software rasterization.

  http://www.chromium.org/developers/design-documents/rendering-benchmarks"""
  page_set = page_sets.ToughCompositorCasesPageSet

  def SetExtraBrowserOptions(self, options):
    super(ThreadTimesCompositorCases, self).SetExtraBrowserOptions(options)
    silk_flags.CustomizeBrowserOptionsForSoftwareRasterization(options)

  @classmethod
  def Name(cls):
    return 'thread_times.tough_compositor_cases'

  def GetExpectations(self):
    class StoryExpectations(story.expectations.StoryExpectations):
      def SetExpectations(self):
        pass # Nothing disabled.
    return StoryExpectations()


@benchmark.Owner(emails=['skyostil@chromium.org'])
class ThreadTimesKeyIdlePowerCases(_ThreadTimes):
  """Measures timeline metrics for sites that should be idle in foreground
  and background scenarios. The metrics are per-second rather than per-frame."""
  page_set = page_sets.KeyIdlePowerCasesPageSet

  @classmethod
  def Name(cls):
    return 'thread_times.key_idle_power_cases'

  @classmethod
  def ValueCanBeAddedPredicate(cls, value, _):
    # Only report per-second metrics.
    return 'per_frame' not in value.name and 'mean_frame' not in value.name

  def GetExpectations(self):
    class StoryExpectations(story.expectations.StoryExpectations):
      def SetExpectations(self):
        self.PermanentlyDisableBenchmark(
            [story.expectations.ALL_DESKTOP], 'Mobile Benchmark')
    return StoryExpectations()


class ThreadTimesKeyNoOpCases(_ThreadTimes):
  """Measures timeline metrics for common interactions and behaviors that should
  have minimal cost. The metrics are per-second rather than per-frame."""
  page_set = page_sets.KeyNoOpCasesPageSet

  @classmethod
  def Name(cls):
    return 'thread_times.key_noop_cases'

  @classmethod
  def ValueCanBeAddedPredicate(cls, value, _):
    # Only report per-second metrics.
    return 'per_frame' not in value.name and 'mean_frame' not in value.name

  def GetExpectations(self):
    class StoryExpectations(story.expectations.StoryExpectations):
      def SetExpectations(self):
        self.PermanentlyDisableBenchmark(
            [story.expectations.ALL_DESKTOP], 'Mobile Benchmark')
    return StoryExpectations()


@benchmark.Owner(emails=['tdresser@chromium.org'])
class ThreadTimesToughScrollingCases(_ThreadTimes):
  """Measure timeline metrics while performing smoothness action on tough
  scrolling cases."""
  page_set = page_sets.ToughScrollingCasesPageSet

  @classmethod
  def Name(cls):
    return 'thread_times.tough_scrolling_cases'

  def GetExpectations(self):
    class StoryExpectations(story.expectations.StoryExpectations):
      def SetExpectations(self):
        pass # Nothing disabled.
    return StoryExpectations()
