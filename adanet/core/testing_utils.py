"""Test utilities for AdaNet single graph implementation.

Copyright 2018 The AdaNet Authors. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import shutil

from absl.testing import parameterized
from adanet.core.architecture import _Architecture
from adanet.core.ensemble import ComplexityRegularized
from adanet.core.ensemble import WeightedSubnetwork
from adanet.core.ensemble_builder import _EnsembleSpec
from adanet.core.subnetwork import Subnetwork
import tensorflow as tf


def dummy_tensor(shape=(), random_seed=42):
  """Returns a randomly initialized tensor."""

  return tf.Variable(
      tf.random_normal(shape=shape, seed=random_seed),
      trainable=False).read_value()


class ExportOutputKeys(object):
  """Different export output keys for the dummy ensemble builder."""

  CLASSIFICATION_CLASSES = "classification_classes"
  CLASSIFICATION_SCORES = "classification_scores"
  REGRESSION = "regression"
  PREDICTION = "prediction"
  INVALID = "invalid"


def dummy_ensemble_spec(name,
                        random_seed=42,
                        num_subnetworks=1,
                        bias=0.,
                        loss=None,
                        adanet_loss=None,
                        eval_metrics=None,
                        dict_predictions=False,
                        export_output_key=None,
                        subnetwork_builders=None,
                        train_op=None):
  """Creates a dummy `_EnsembleSpec` instance.

  Args:
    name: _EnsembleSpec's name.
    random_seed: A scalar random seed.
    num_subnetworks: The number of fake subnetworks in this ensemble.
    bias: Bias value.
    loss: Float loss to return. When None, it's picked from a random
      distribution.
    adanet_loss: Float AdaNet loss to return. When None, it's picked from a
      random distribution.
    eval_metrics: Optional eval metrics tuple of (metric_fn, tensor args).
    dict_predictions: Boolean whether to return predictions as a dictionary of
      `Tensor` or just a single float `Tensor`.
    export_output_key: An `ExportOutputKeys` for faking export outputs.
    subnetwork_builders: List of `adanet.subnetwork.Builder` objects.
    train_op: A train op.

  Returns:
    A dummy `_EnsembleSpec` instance.
  """

  if loss is None:
    loss = dummy_tensor([], random_seed)

  if adanet_loss is None:
    adanet_loss = dummy_tensor([], random_seed * 2)
  else:
    adanet_loss = tf.convert_to_tensor(adanet_loss)

  logits = dummy_tensor([], random_seed * 3)
  if dict_predictions:
    predictions = {
        "logits": logits,
        "classes": tf.cast(tf.abs(logits), dtype=tf.int64)
    }
  else:
    predictions = logits
  weighted_subnetworks = [
      WeightedSubnetwork(
          name=name,
          iteration_number=1,
          logits=dummy_tensor([2, 1], random_seed * 4),
          weight=dummy_tensor([2, 1], random_seed * 4),
          subnetwork=Subnetwork(
              last_layer=dummy_tensor([1, 2], random_seed * 4),
              logits=dummy_tensor([2, 1], random_seed * 4),
              complexity=1.,
              persisted_tensors={}))
  ]

  export_outputs = _dummy_export_outputs(export_output_key, logits, predictions)
  bias = tf.constant(bias)
  return _EnsembleSpec(
      name=name,
      ensemble=ComplexityRegularized(
          weighted_subnetworks=weighted_subnetworks * num_subnetworks,
          bias=bias,
          logits=logits,
      ),
      architecture=_Architecture(),
      subnetwork_builders=subnetwork_builders,
      predictions=predictions,
      loss=loss,
      adanet_loss=adanet_loss,
      train_op=train_op,
      eval_metrics=eval_metrics,
      export_outputs=export_outputs)


def _dummy_export_outputs(export_output_key, logits, predictions):
  """Returns a dummy export output dictionary for the given key."""

  export_outputs = None
  if export_output_key == ExportOutputKeys.CLASSIFICATION_CLASSES:
    export_outputs = {
        export_output_key:
            tf.estimator.export.ClassificationOutput(
                classes=tf.as_string(logits))
    }
  elif export_output_key == ExportOutputKeys.CLASSIFICATION_SCORES:
    export_outputs = {
        export_output_key:
            tf.estimator.export.ClassificationOutput(scores=logits)
    }
  elif export_output_key == ExportOutputKeys.REGRESSION:
    export_outputs = {
        export_output_key: tf.estimator.export.RegressionOutput(value=logits)
    }
  elif export_output_key == ExportOutputKeys.PREDICTION:
    export_outputs = {
        export_output_key:
            tf.estimator.export.PredictOutput(outputs=predictions)
    }
  elif export_output_key == ExportOutputKeys.INVALID:
    export_outputs = {export_output_key: predictions}
  return export_outputs


def dummy_estimator_spec(loss=None,
                         random_seed=42,
                         eval_metric_ops=None):
  """Creates a dummy `EstimatorSpec` instance.

  Args:
    loss: Float loss to return. When None, it's picked from a random
      distribution.
    random_seed: Scalar seed for random number generators.
    eval_metric_ops: Optional dictionary of metric ops.

  Returns:
    A `EstimatorSpec` instance.
  """

  if loss is None:
    loss = dummy_tensor([], random_seed)
  predictions = dummy_tensor([], random_seed * 2)
  return tf.estimator.EstimatorSpec(
      mode=tf.estimator.ModeKeys.TRAIN,
      predictions=predictions,
      loss=loss,
      train_op=tf.no_op(),
      eval_metric_ops=eval_metric_ops)


def dummy_input_fn(features, labels):
  """Returns an input_fn that returns feature and labels `Tensors`."""

  def _input_fn(params=None):
    del params  # Unused.

    input_features = {"x": tf.constant(features, name="x")}
    input_labels = tf.constant(labels, name="y")
    return input_features, input_labels

  return _input_fn


def dataset_input_fn(features=8., labels=9.):
  """Returns feature and label `Tensors` via a `Dataset`."""

  def _input_fn(params=None):
    """The `Dataset` input_fn which will be returned."""

    del params  # Unused.

    input_features = tf.data.Dataset.from_tensors(
        [features]).make_one_shot_iterator().get_next()
    if labels is not None:
      input_labels = tf.data.Dataset.from_tensors(
          [labels]).make_one_shot_iterator().get_next()
    else:
      input_labels = None
    return {"x": input_features}, input_labels

  return _input_fn


def head():
  return tf.contrib.estimator.regression_head(
      loss_reduction=tf.losses.Reduction.SUM_OVER_BATCH_SIZE)


class AdanetTestCase(parameterized.TestCase, tf.test.TestCase):
  """A parameterized `TestCase` that manages a test subdirectory."""

  def setUp(self):
    super(AdanetTestCase, self).setUp()
    # Setup and cleanup test directory.
    self.test_subdirectory = os.path.join(tf.flags.FLAGS.test_tmpdir, self.id())
    shutil.rmtree(self.test_subdirectory, ignore_errors=True)
    os.makedirs(self.test_subdirectory)

  def tearDown(self):
    super(AdanetTestCase, self).tearDown()
    shutil.rmtree(self.test_subdirectory, ignore_errors=True)
