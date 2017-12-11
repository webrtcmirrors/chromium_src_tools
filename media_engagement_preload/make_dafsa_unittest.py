#!/usr/bin/env python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import sys
import unittest
import make_dafsa


class ToDafsaTest(unittest.TestCase):
  def testEmptyInput(self):
    """Tests exception is thrown at empty input."""
    words = ()
    self.assertRaises(make_dafsa.InputError, make_dafsa.to_dafsa, words)

  def testNonASCII(self):
    """Tests exception is thrown if illegal characters are used."""
    words1 = ( chr(0x1F) + 'a1', )
    self.assertRaises(make_dafsa.InputError, make_dafsa.to_dafsa, words1)

    words2 = ( 'a' + chr(0x1F) + '1', )
    self.assertRaises(make_dafsa.InputError, make_dafsa.to_dafsa, words2)

    words3 = ( chr(0x80) + 'a1', )
    self.assertRaises(make_dafsa.InputError, make_dafsa.to_dafsa, words3)

    words4 = ( 'a' + chr(0x80) + '1', )
    self.assertRaises(make_dafsa.InputError, make_dafsa.to_dafsa, words4)

  def testChar(self):
    """Tests a DAFSA can be created from a single character domain name."""
    words = [ 'a0' ]
    node2 = ( chr(0), [ None ] )
    node1 = ( 'a', [ node2 ] )
    source = [ node1 ]
    self.assertEqual(make_dafsa.to_dafsa(words), source)

  def testChars(self):
    """Tests a DAFSA can be created from a multi character domain name."""
    words = [ 'ab0' ]
    node3 = ( chr(0), [ None ] )
    node2 = ( 'b', [ node3 ] )
    node1 = ( 'a', [ node2 ] )
    source = [ node1 ]
    self.assertEqual(make_dafsa.to_dafsa(words), source)

  def testWords(self):
    """Tests a DAFSA can be created from a sequence of domain names."""
    words = [ 'a0', 'b1' ]
    node4 = ( chr(1), [ None ] )
    node3 = ( 'b', [ node4 ] )
    node2 = ( chr(0), [ None ] )
    node1 = ( 'a', [ node2 ] )
    source = [ node1, node3 ]
    self.assertEqual(make_dafsa.to_dafsa(words), source)


class ToWordsTest(unittest.TestCase):
  def testSink(self):
    """Tests the sink is exapnded to a list with an empty string."""
    node1 = None
    words = [ '' ]
    self.assertEqual(make_dafsa.to_words(node1), words)

  def testSingleNode(self):
    """Tests a single node is expanded to a list with the label string."""

    # 'ab' -> [ 'ab' ]

    node1 = ( 'ab', [ None ] )
    words = [ 'ab' ]
    self.assertEqual(make_dafsa.to_words(node1), words)

  def testChain(self):
    """Tests a sequence of nodes are preoperly expanded."""

    # 'ab' -> 'cd' => [ 'abcd' ]

    node2 = ( 'cd', [ None ] )
    node1 = ( 'ab', [ node2 ] )
    words = [ 'abcd' ]
    self.assertEqual(make_dafsa.to_words(node1), words)

  def testInnerTerminator(self):
    """Tests a sequence with an inner terminator is expanded to two strings."""

    # 'a' -> 'b'
    #   \       => [ 'ab', 'a' ]
    #  {sink}

    node2 = ( 'b', [ None ] )
    node1 = ( 'a', [ node2, None ] )
    words = [ 'ab', 'a' ]
    self.assertEqual(make_dafsa.to_words(node1), words)

  def testDiamond(self):
    """Tests a diamond can be expanded to a word list."""

    #   'cd'
    #   /  \
    # 'ab' 'gh'
    #   \  /
    #   'ef'

    node4 = ( 'gh', [ None ] )
    node3 = ( 'ef', [ node4 ] )
    node2 = ( 'cd', [ node4 ] )
    node1 = ( 'ab', [ node2, node3 ] )
    words = [ 'abcdgh', 'abefgh' ]
    self.assertEqual(make_dafsa.to_words(node1), words)


class JoinLabelsTest(unittest.TestCase):
  def testLabel(self):
    """Tests a single label passes unchanged."""

    # 'a'  =>  'a'

    node1 = ( 'a', [ None ] )
    source = [ node1 ]
    self.assertEqual(make_dafsa.join_labels(source), source)

  def testInnerTerminator(self):
    """Tests a sequence with an inner terminator passes unchanged."""

    # 'a' -> 'b'    'a' -> 'b'
    #   \       =>    \
    #  {sink}        {sink}

    node2 = ( 'b', [ None ] )
    node1 = ( 'a', [ node2, None ] )
    source = [ node1 ]
    self.assertEqual(make_dafsa.join_labels(source), source)

  def testLabels(self):
    """Tests a sequence of labels can be joined."""

    # 'a' -> 'b'  =>  'ab'

    node2 = ( 'b', [ None ] )
    node1 = ( 'a', [ node2 ] )
    source1 = [ node1 ]
    node3 = ( 'ab', [ None ] )
    source2 = [ node3 ]
    self.assertEqual(make_dafsa.join_labels(source1), source2)

  def testCompositeLabels(self):
    """Tests a sequence of multi character labels can be joined."""

    # 'ab' -> 'cd'  =>  'abcd'

    node2 = ( 'cd', [ None ] )
    node1 = ( 'ab', [ node2 ] )
    source1 = [ node1 ]
    node3 = ( 'abcd', [ None ] )
    source2 = [ node3 ]
    self.assertEqual(make_dafsa.join_labels(source1), source2)

  def testAtomicTrie(self):
    """Tests a trie formed DAFSA with atomic labels passes unchanged."""

    #   'b'       'b'
    #   /         /
    # 'a'   =>  'a'
    #   \         \
    #   'c'       'c'

    node3 = ( 'c', [ None ] )
    node2 = ( 'b', [ None ] )
    node1 = ( 'a', [ node2, node3 ] )
    source = [ node1 ]
    self.assertEqual(make_dafsa.join_labels(source), source)

  def testReverseAtomicTrie(self):
    """Tests a reverse trie formed DAFSA with atomic labels passes unchanged."""

    # 'a'        'a'
    #   \          \
    #   'c'  =>    'c'
    #   /          /
    # 'b'        'b'

    node3 = ( 'c', [ None ] )
    node2 = ( 'b', [ node3 ] )
    node1 = ( 'a', [ node3 ] )
    source = [ node1, node2 ]
    self.assertEqual(make_dafsa.join_labels(source), source)

  def testChainedTrie(self):
    """Tests a trie formed DAFSA with chained labels can be joined."""

    #          'c' -> 'd'         'cd'
    #          /                  /
    # 'a' -> 'b'           =>  'ab'
    #          \                  \
    #          'e' -> 'f'         'ef'

    node6 = ( 'f', [ None ] )
    node5 = ( 'e', [ node6 ] )
    node4 = ( 'd', [ None ] )
    node3 = ( 'c', [ node4 ] )
    node2 = ( 'b', [ node3, node5 ] )
    node1 = ( 'a', [ node2 ] )
    source1 = [ node1 ]
    node9 = ( 'ef', [ None ] )
    node8 = ( 'cd', [ None ] )
    node7 = ( 'ab', [ node8, node9 ] )
    source2 = [ node7 ]
    self.assertEqual(make_dafsa.join_labels(source1), source2)

  def testReverseChainedTrie(self):
    """Tests a reverse trie formed DAFSA with chained labels can be joined."""

    # 'a' -> 'b'               'ab'
    #          \                  \
    #          'e' -> 'f'  =>     'ef'
    #          /                  /
    # 'c' -> 'd'               'cd'

    node6 = ( 'f', [ None ] )
    node5 = ( 'e', [ node6 ] )
    node4 = ( 'd', [ node5 ] )
    node3 = ( 'c', [ node4 ] )
    node2 = ( 'b', [ node5 ] )
    node1 = ( 'a', [ node2 ] )
    source1 = [ node1, node3 ]
    node9 = ( 'ef', [ None ] )
    node8 = ( 'cd', [ node9 ] )
    node7 = ( 'ab', [ node9 ] )
    source2 = [ node7, node8 ]
    self.assertEqual(make_dafsa.join_labels(source1), source2)


class JoinSuffixesTest(unittest.TestCase):
  def testSingleLabel(self):
    """Tests a single label passes unchanged."""

    # 'a'  =>  'a'

    node1 = ( 'a', [ None ] )
    source = [ node1 ]
    self.assertEqual(make_dafsa.join_suffixes(source), source)

  def testInnerTerminator(self):
    """Tests a sequence with an inner terminator passes unchanged."""

    # 'a' -> 'b'    'a' -> 'b'
    #   \       =>    \
    #  {sink}        {sink}

    node2 = ( 'b', [ None ] )
    node1 = ( 'a', [ node2, None ] )
    source = [ node1 ]
    self.assertEqual(make_dafsa.join_suffixes(source), source)

  def testDistinctTrie(self):
    """Tests a trie formed DAFSA with distinct labels passes unchanged."""

    #   'b'       'b'
    #   /         /
    # 'a'   =>  'a'
    #   \         \
    #   'c'       'c'

    node3 = ( 'c', [ None ] )
    node2 = ( 'b', [ None ] )
    node1 = ( 'a', [ node2, node3 ] )
    source = [ node1 ]
    self.assertEqual(make_dafsa.join_suffixes(source), source)

  def testReverseDistinctTrie(self):
    """Tests a reverse trie formed DAFSA with distinct labels passes unchanged.
    """

    # 'a'        'a'
    #   \          \
    #   'c'  =>    'c'
    #   /          /
    # 'b'        'b'

    node3 = ( 'c', [ None ] )
    node2 = ( 'b', [ node3 ] )
    node1 = ( 'a', [ node3 ] )
    source = [ node1, node2 ]
    self.assertEqual(make_dafsa.join_suffixes(source), source)

  def testJoinTwoHeads(self):
    """Tests two heads can be joined even if there is something else between."""

    # 'a'       ------'a'
    #                 /
    # 'b'  =>  'b'   /
    #               /
    # 'a'       ---
    #
    # The picture above should shows that the new version should have just one
    # instance of the node with label 'a'.

    node3 = ( 'a', [ None ] )
    node2 = ( 'b', [ None ] )
    node1 = ( 'a', [ None ] )
    source1 = [ node1, node2, node3 ]
    source2 = make_dafsa.join_suffixes(source1)

    # Both versions should expand to the same content.
    self.assertEqual(source1, source2)
    # But the new version should have just one instance of 'a'.
    self.assertIs(source2[0], source2[2])

  def testJoinTails(self):
    """Tests tails can be joined."""

    # 'a' -> 'c'      'a'
    #                   \
    #             =>    'c'
    #                   /
    # 'b' -> 'c'      'b'

    node4 = ( 'c', [ None ] )
    node3 = ( 'b', [ node4 ] )
    node2 = ( 'c', [ None ] )
    node1 = ( 'a', [ node2 ] )
    source1 = [ node1, node3 ]
    source2 = make_dafsa.join_suffixes(source1)

    # Both versions should expand to the same content.
    self.assertEqual(source1, source2)
    # But the new version should have just one tail.
    self.assertIs(source2[0][1][0], source2[1][1][0])

  def testMakeRecursiveTrie(self):
    """Tests recursive suffix join."""

    # 'a' -> 'e' -> 'g'     'a'
    #                         \
    #                         'e'
    #                         / \
    # 'b' -> 'e' -> 'g'     'b'  \
    #                             \
    #                   =>        'g'
    #                             /
    # 'c' -> 'f' -> 'g'     'c'  /
    #                         \ /
    #                         'f'
    #                         /
    # 'd' -> 'f' -> 'g'     'd'

    node7 = ( 'g', [ None ] )
    node6 = ( 'f', [ node7 ] )
    node5 = ( 'e', [ node7 ] )
    node4 = ( 'd', [ node6 ] )
    node3 = ( 'c', [ node6 ] )
    node2 = ( 'b', [ node5 ] )
    node1 = ( 'a', [ node5 ] )
    source1 = [ node1, node2, node3, node4 ]
    source2 = make_dafsa.join_suffixes(source1)

    # Both versions should expand to the same content.
    self.assertEqual(source1, source2)
    # But the new version should have just one 'e'.
    self.assertIs(source2[0][1][0], source2[1][1][0])
    # And one 'f'.
    self.assertIs(source2[2][1][0], source2[3][1][0])
    # And one 'g'.
    self.assertIs(source2[0][1][0][1][0], source2[2][1][0][1][0])

  def testMakeDiamond(self):
    """Test we can join suffixes of a trie."""

    #   'b' -> 'd'        'b'
    #   /                 / \
    # 'a'           =>  'a' 'd'
    #   \                 \ /
    #   'c' -> 'd'        'c'

    node5 = ( 'd', [ None ] )
    node4 = ( 'c', [ node5 ] )
    node3 = ( 'd', [ None ] )
    node2 = ( 'b', [ node3 ] )
    node1 = ( 'a', [ node2, node4 ] )
    source1 = [ node1 ]
    source2 = make_dafsa.join_suffixes(source1)

    # Both versions should expand to the same content.
    self.assertEqual(source1, source2)
    # But the new version should have just one 'd'.
    self.assertIs(source2[0][1][0][1][0], source2[0][1][1][1][0])

  def testJoinOneChild(self):
    """Tests that we can join some children but not all."""

    #   'c'            ----'c'
    #   /            /     /
    # 'a'          'a'    /
    #   \            \   /
    #   'd'          'd'/
    #          =>      /
    #   'c'           /
    #   /            /
    # 'b'          'b'
    #   \            \
    #   'e'          'e'

    node6 = ( 'e', [ None ] )
    node5 = ( 'c', [ None ] )
    node4 = ( 'b', [ node5, node6 ] )
    node3 = ( 'd', [ None ] )
    node2 = ( 'c', [ None ] )
    node1 = ( 'a', [ node2, node3 ] )
    source1 = [ node1, node4 ]
    source2 = make_dafsa.join_suffixes(source1)

    # Both versions should expand to the same content.
    self.assertEqual(source1, source2)
    # But the new version should have just one 'c'.
    self.assertIs(source2[0][1][0], source2[1][1][0])


class ReverseTest(unittest.TestCase):
  def testAtomicLabel(self):
    """Tests an atomic label passes unchanged."""

    # 'a'  =>  'a'

    node1 = ( 'a', [ None ] )
    source = [ node1 ]
    self.assertEqual(make_dafsa.reverse(source), source)

  def testLabel(self):
    """Tests that labels are reversed."""

    # 'ab'  =>  'ba'

    node1 = ( 'ab', [ None ] )
    source1 = [ node1 ]
    node2 = ( 'ba', [ None ] )
    source2 = [ node2 ]
    self.assertEqual(make_dafsa.reverse(source1), source2)

  def testChain(self):
    """Tests that edges are reversed."""

    # 'a' -> 'b'  =>  'b' -> 'a'

    node2 = ( 'b', [ None ] )
    node1 = ( 'a', [ node2 ] )
    source1 = [ node1 ]
    node4 = ( 'a', [ None ] )
    node3 = ( 'b', [ node4 ] )
    source2 = [ node3 ]
    self.assertEqual(make_dafsa.reverse(source1), source2)

  def testInnerTerminator(self):
    """Tests a sequence with an inner terminator can be reversed."""

    # 'a' -> 'b'    'b' -> 'a'
    #   \       =>         /
    #  {sink}        ------

    node2 = ( 'b', [ None ] )
    node1 = ( 'a', [ node2, None ] )
    source1 = [ node1 ]
    node4 = ( 'a', [ None ] )
    node3 = ( 'b', [ node4 ] )
    source2 = [ node3, node4 ]
    self.assertEqual(make_dafsa.reverse(source1), source2)

  def testAtomicTrie(self):
    """Tests a trie formed DAFSA can be reversed."""

    #   'b'     'b'
    #   /         \
    # 'a'   =>    'a'
    #   \         /
    #   'c'     'c'

    node3 = ( 'c', [ None ] )
    node2 = ( 'b', [ None ] )
    node1 = ( 'a', [ node2, node3 ] )
    source1 = [ node1 ]
    node6 = ( 'a', [ None ] )
    node5 = ( 'c', [ node6 ] )
    node4 = ( 'b', [ node6 ] )
    source2 = [ node4, node5 ]
    self.assertEqual(make_dafsa.reverse(source1), source2)

  def testReverseAtomicTrie(self):
    """Tests a reverse trie formed DAFSA can be reversed."""

    # 'a'          'a'
    #   \          /
    #   'c'  =>  'c'
    #   /          \
    # 'b'          'b'

    node3 = ( 'c', [ None ] )
    node2 = ( 'b', [ node3 ] )
    node1 = ( 'a', [ node3 ] )
    source1 = [ node1, node2 ]
    node6 = ( 'b', [ None ] )
    node5 = ( 'a', [ None ] )
    node4 = ( 'c', [ node5, node6 ] )
    source2 = [ node4 ]
    self.assertEqual(make_dafsa.reverse(source1), source2)

  def testDiamond(self):
    """Tests we can reverse both edges and nodes in a diamond."""

    #   'cd'           'dc'
    #   /  \           /  \
    # 'ab' 'gh'  =>  'hg' 'ba'
    #   \  /           \  /
    #   'ef'           'fe'

    node4 = ( 'gh', [ None ] )
    node3 = ( 'ef', [ node4 ] )
    node2 = ( 'cd', [ node4 ] )
    node1 = ( 'ab', [ node2, node3 ] )
    source1 = [ node1 ]
    node8 = ( 'ba', [ None ] )
    node7 = ( 'fe', [ node8 ] )
    node6 = ( 'dc', [ node8 ] )
    node5 = ( 'hg', [ node6, node7 ] )
    source2 = [ node5 ]
    self.assertEqual(make_dafsa.reverse(source1), source2)


class TopSortTest(unittest.TestCase):
  def testNode(self):
    """Tests a DAFSA with one node can be sorted."""

    # 'a'  =>  [ 'a' ]

    node1 = ( 'a', [ None ] )
    source = [ node1 ]
    nodes = [ node1 ]
    self.assertEqual(make_dafsa.top_sort(source), nodes)

  def testDiamond(self):
    """Tests nodes in a diamond can be sorted."""

    #   'b'
    #   / \
    # 'a' 'd'
    #   \ /
    #   'c'

    node4 = ( 'd', [ None ] )
    node3 = ( 'c', [ node4 ] )
    node2 = ( 'b', [ node4 ] )
    node1 = ( 'a', [ node2, node3 ] )
    source = [ node1 ]
    nodes = make_dafsa.top_sort(source)
    self.assertLess(nodes.index(node1), nodes.index(node2))
    self.assertLess(nodes.index(node2), nodes.index(node4))
    self.assertLess(nodes.index(node3), nodes.index(node4))


class EncodePrefixTest(unittest.TestCase):
  def testChar(self):
    """Tests to encode a single character prefix."""
    label = 'a'
    bytes = [ ord('a') ]
    self.assertEqual(make_dafsa.encode_prefix(label), bytes)

  def testChars(self):
    """Tests to encode a multi character prefix."""
    label = 'ab'
    bytes = [ ord('b'), ord('a') ]
    self.assertEqual(make_dafsa.encode_prefix(label), bytes)


class EncodeLabelTest(unittest.TestCase):
  def testChar(self):
    """Tests to encode a single character label."""
    label = 'a'
    bytes = [ ord('a') + 0x80 ]
    self.assertEqual(make_dafsa.encode_label(label), bytes)

  def testChars(self):
    """Tests to encode a multi character label."""
    label = 'ab'
    bytes = [ ord('b') + 0x80, ord('a') ]
    self.assertEqual(make_dafsa.encode_label(label), bytes)


class EncodeLinksTest(unittest.TestCase):
  def testEndLabel(self):
    """Tests to encode link to the sink."""
    children = [ None ]
    offsets = {}
    bytes = 0
    output = []
    self.assertEqual(make_dafsa.encode_links(children, offsets, bytes),
                      output)

  def testOneByteOffset(self):
    """Tests to encode a single one byte offset."""
    node = ( '', [ None ] )
    children = [ node ]
    offsets = { id(node) : 2 }
    bytes = 5
    output = [ 132 ]
    self.assertEqual(make_dafsa.encode_links(children, offsets, bytes),
                      output)

  def testOneByteOffsets(self):
    """Tests to encode a sequence of one byte offsets."""
    node1 = ( '', [ None ] )
    node2 = ( '', [ None ] )
    children = [ node1, node2 ]
    offsets = { id(node1) : 2, id(node2) : 1 }
    bytes = 5
    output = [ 129, 5 ]
    self.assertEqual(make_dafsa.encode_links(children, offsets, bytes),
                      output)

  def testTwoBytesOffset(self):
    """Tests to encode a single two byte offset."""
    node = ( '', [ None ] )
    children = [ node ]
    offsets = { id(node) : 2 }
    bytes = 1005
    output = [ 237, 195]
    self.assertEqual(make_dafsa.encode_links(children, offsets, bytes),
                      output)

  def testTwoBytesOffsets(self):
    """Tests to encode a sequence of two byte offsets."""
    node1 = ( '', [ None ] )
    node2 = ( '', [ None ] )
    node3 = ( '', [ None ] )
    children = [ node1, node2, node3 ]
    offsets = { id(node1) : 1002, id(node2) : 2, id(node3) : 2002 }
    bytes = 3005
    output = [ 232, 195, 232, 67, 241, 67 ]
    self.assertEqual(make_dafsa.encode_links(children, offsets, bytes),
                      output)

  def testThreeBytesOffset(self):
    """Tests to encode a single three byte offset."""
    node = ( '', [ None ] )
    children = [ node ]
    offsets = { id(node) : 2 }
    bytes = 100005
    output = [ 166, 134, 225 ]
    self.assertEqual(make_dafsa.encode_links(children, offsets, bytes),
                      output)

  def testThreeBytesOffsets(self):
    """Tests to encode a sequence of three byte offsets."""
    node1 = ( '', [ None ] )
    node2 = ( '', [ None ] )
    node3 = ( '', [ None ] )
    children = [ node1, node2, node3 ]
    offsets = { id(node1) : 100002, id(node2) : 2, id(node3) : 200002 }
    bytes = 300005
    output = [ 160, 134, 225, 160, 134, 97, 172, 134, 97 ]
    self.assertEqual(make_dafsa.encode_links(children, offsets, bytes),
                      output)

  def testOneTwoThreeBytesOffsets(self):
    """Tests to encode offsets of different sizes."""
    node1 = ( '', [ None ] )
    node2 = ( '', [ None ] )
    node3 = ( '', [ None ] )
    children = [ node1, node2, node3 ]
    offsets = { id(node1) : 10003, id(node2) : 10002, id(node3) : 100002 }
    bytes = 300005
    output = [ 129, 143, 95, 97, 74, 13, 99 ]
    self.assertEqual(make_dafsa.encode_links(children, offsets, bytes),
                      output)


class ExamplesTest(unittest.TestCase):
  def testExample1(self):
    """Tests Example 1 from make_dafsa.py."""
    infile = '["https://www.example.com:8081", "http://www.example.org"]'
    outfile = ("\n3\x81htt\xf0\x02\x93://www.example.or\xe7\x99"
               "s://www.example.com:8081\x80")
    self.assertEqual(make_dafsa.words_to_proto(make_dafsa.parse_json(infile)),
                      outfile)

  def testExample2(self):
    """Tests Example 2 from make_dafsa.py."""
    infile = '["https://www.example.org", "http://www.google.com"]'
    outfile = ("\n-\x81htt\xf0\x02\x92://www.google.co\xed\x94"
               "s://www.example.org\x80")
    self.assertEqual(make_dafsa.words_to_proto(make_dafsa.parse_json(infile)),
                      outfile)

  def testExample3(self):
    """Tests Example 3 from make_dafsa.py."""
    self.assertRaises(make_dafsa.InputError, make_dafsa.parse_json, "badinput")


if __name__ == '__main__':
  unittest.main()
