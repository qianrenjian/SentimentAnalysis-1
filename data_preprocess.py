#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2019/10/15 16:12
# @Author  : wutt
# @File    : data_preprocess.py
# corpus preprocessing ,define dataprocessor for making corpus into examples
import pandas as pd
import os
import csv
import sys
import logging
import pickle
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt

from up_sampling import up_sampling, eda
import args
logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s',level=logging.INFO)

# 无图形界面需要加，否则plt报错
plt.switch_backend('agg')


class DataProcessor(object):
    """Base class for data converters for sequence classification data sets."""

    def get_train_examples(self, data_dir):
        """Gets a collection of `InputExample`s for the train set."""
        raise NotImplementedError()

    def get_dev_examples(self, data_dir):
        """Gets a collection of `InputExample`s for the dev set."""
        raise NotImplementedError()

    def get_labels(self):
        """Gets the list of labels for this data set."""
        raise NotImplementedError()

    @classmethod
    def _read_csv(cls, input_file):#, quotechar=None):
        """Reads a comma separated value file."""
        with open(input_file, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=",")#, quotechar=quotechar)
            lines = []
            for line in reader:
                if sys.version_info[0] == 2:
                    line = list(unicode(cell, 'utf-8') for cell in line)
                # if len(line) != 3:
                #     print(line)
                lines.append(line)
            return lines

class InputExample(object):
    """A single training/test example for simple sequence classification."""

    def __init__(self, guid, text_a, text_b=None, label=None):
        """Constructs a InputExample.

        Args:
            guid: Unique id for the example.
            text_a: string. The untokenized text of the first sequence. For single
            sequence tasks, only this sequence must be specified.
            text_b: (Optional) string. The untokenized text of the second sequence.
            Only must be specified for sequence pair tasks.
            label: (Optional) string. The label of the example. This should be
            specified for train and dev examples, but not for test examples.
        """
        self.guid = guid
        # TODO : new added for DA-------------------------------------------------------
        if label == '0' or label == '2':
            self.text_a = eda(text_a, args.alpha_rs)
        else:
            self.text_a = text_a
        # TODO : end--------------------------------------------------------------------
        # self.text_a = text_a
        self.text_b = text_b
        self.label = label

# TODO: 分段特征
class InputFeatures(object):
    def __init__(self,
                 example_id,
                 choices_features,
                 label

    ):
        self.example_id = example_id
        self.choices_features = [
            {
                'input_ids': input_ids,
                'input_mask': input_mask,
                'segment_ids': segment_ids
            }
            for _, input_ids, input_mask, segment_ids in choices_features
        ]
        self.label = label

# TODO: 未分段特征
# class InputFeatures(object):
#     """A single set of features of data."""
#
#     def __init__(self, input_ids, input_mask, segment_ids, label_id):
#         self.input_ids = input_ids
#         self.input_mask = input_mask
#         self.segment_ids = segment_ids
#         self.label_id = label_id

class SentiAnalysisProcessor(DataProcessor):
    """Processor for the Sentiment data set (GLUE version)."""

    def get_train_examples(self, data_dir):
        """See base class."""
        return self._create_examples(
            self._read_csv(os.path.join(data_dir, args.TRAIN_US_CORPUS_FILE)), "train")

    def get_dev_examples(self, data_dir):
        """See base class."""
        return self._create_examples(
            self._read_csv(os.path.join(data_dir, args.DEV_US_CORPUS_FILE)),
            "dev_matched")

    def get_test_examples(self, data_dir):
        """See base class."""
        return self._create_examples(
            self._read_csv(os.path.join(data_dir, args.TEST_CORPUS_FILE)),
            "test")

    def get_labels(self):
        """See base class."""
        return args.labels#["0", "1", "2"]

    def _create_examples(self, lines, set_type):
        """Creates examples for the training and dev sets."""
        examples = []
        for (i, line) in enumerate(lines):
            if i == 0:
                continue
            guid = "%s-%s" % (set_type, line[0])#line[0]为行index
            text_a = line[1]
            if set_type == 'test':
                examples.append(
                    InputExample(guid=guid, text_a=text_a, text_b=None))
            else:
                label = line[2]
                examples.append(
                    InputExample(guid=guid, text_a=text_a, text_b=None, label=label))
        return examples

def _truncate_seq_pair(tokens_a, tokens_b, max_length):
    """Truncates a sequence pair in place to the maximum length."""

    # This is a simple heuristic which will always truncate the longer sequence
    # one token at a time. This makes more sense than truncating an equal percent
    # of tokens from each, since if one sequence is very short then each token
    # that's truncated likely contains more information than a longer sequence.
    while True:
        total_length = len(tokens_a) + len(tokens_b)
        if total_length <= max_length:
            break
        if len(tokens_a) > len(tokens_b):
            tokens_a.pop()
        else:
            tokens_b.pop()

# TODO: 分段样本转特征
def convert_examples_to_features(examples, max_seq_length, split_num,
                                 tokenizer, mode,
                                 cls_token_at_end=False, pad_on_left=False,
                                 cls_token='[CLS]', sep_token='[SEP]', pad_token=0,
                                 sequence_a_segment_id=0, sequence_b_segment_id=1,
                                 cls_token_segment_id=1, pad_token_segment_id=0,
                                 mask_padding_with_zero=True):
    """Loads a data file into a list of `InputBatch`s."""

    # Swag is a multiple choice task. To perform this task using Bert,
    # we will use the formatting proposed in "Improving Language
    # Understanding by Generative Pre-Training" and suggested by
    # @jacobdevlin-google in this issue
    # https://github.com/google-research/bert/issues/38.
    #
    # Each choice will correspond to a sample on which we run the
    # inference. For a given Swag example, we will create the 4
    # following inputs:
    # - [CLS] context [SEP] choice_1 [SEP]
    # - [CLS] context [SEP] choice_2 [SEP]
    # - [CLS] context [SEP] choice_3 [SEP]
    # - [CLS] context [SEP] choice_4 [SEP]
    # The model will output a single value for each input. To get the
    # final decision of the model, we will run a softmax over these 4
    # outputs.
    features = []
    for example_index, example in enumerate(examples):

        tokens_a = tokenizer.tokenize(example.text_a)

        skip_len = len(tokens_a) / split_num
        choices_features = []
        for i in range(split_num):
            context_tokens_choice = tokens_a[int(i * skip_len):int((i + 1) * skip_len)]

            tokens_b = None
            if example.text_b:
                tokens_b = tokenizer.tokenize(example.text_b)
                # Modifies `tokens_a` and `tokens_b` in place so that the total
                # length is less than the specified length.
                # Account for [CLS], [SEP], [SEP] with "- 3"
                _truncate_seq_pair(context_tokens_choice, tokens_b, max_seq_length - 3)
            else:
                # Account for [CLS] and [SEP] with "- 2"
                if len(context_tokens_choice) > max_seq_length - 2:
                    context_tokens_choice = context_tokens_choice[:(max_seq_length - 2)]

            tokens = context_tokens_choice + [sep_token]
            segment_ids = [sequence_a_segment_id] * len(tokens)

            if tokens_b:
                tokens += tokens_b + [sep_token]
                segment_ids += [sequence_b_segment_id] * (len(tokens_b) + 1)

            if cls_token_at_end:
                tokens = tokens + [cls_token]
                segment_ids = segment_ids + [cls_token_segment_id]
            else:
                tokens = [cls_token] + tokens
                segment_ids = [cls_token_segment_id] + segment_ids

            input_ids = tokenizer.convert_tokens_to_ids(tokens)

            # The mask has 1 for real tokens and 0 for padding tokens. Only real
            # tokens are attended to.
            input_mask = [1 if mask_padding_with_zero else 0] * len(input_ids)

            # Zero-pad up to the sequence length.
            padding_length = max_seq_length - len(input_ids)
            if pad_on_left:
                input_ids = ([pad_token] * padding_length) + input_ids
                input_mask = ([0 if mask_padding_with_zero else 1] * padding_length) + input_mask
                segment_ids = ([pad_token_segment_id] * padding_length) + segment_ids
            else:
                input_ids = input_ids + ([pad_token] * padding_length)
                input_mask = input_mask + ([0 if mask_padding_with_zero else 1] * padding_length)
                segment_ids = segment_ids + ([pad_token_segment_id] * padding_length)

            assert len(input_ids) == max_seq_length
            assert len(input_mask) == max_seq_length
            assert len(segment_ids) == max_seq_length

            choices_features.append((tokens, input_ids, input_mask, segment_ids))

            label = example.label
            if example_index < 1 and mode == 'train':
                logger.info("*** Example ***")
                logger.info("idx: {}".format(example_index))
                logger.info("guid: {}".format(example.guid))
                logger.info("tokens: {}".format(' '.join(tokens).replace('\u2581', '_')))
                logger.info("input_ids: {}".format(' '.join(map(str, input_ids))))
                logger.info("input_mask: {}".format(' '.join(map(str, input_mask))))
                logger.info("segment_ids: {}".format(' '.join(map(str, segment_ids))))
                logger.info("labels: {}".format(label))

        features.append(
            InputFeatures(
                example_id=example.guid,
                choices_features=choices_features,
                label=label
            )
        )

    if mode == "train":
        with open(os.path.join(args.data_dir, args.TRAIN_US_FEATURE_FILE), 'wb') as f:#TRAIN_FEATURE_FILE
            pickle.dump(features, f)
    elif mode == 'dev':
        with open(os.path.join(args.data_dir, args.DEV_US_FEATURE_FILE), 'wb') as f:#DEV_FEATURE_FILE
            pickle.dump(features, f)
    elif mode == 'test':
        with open(os.path.join(args.data_dir, args.TEST_FEATURE_FILE), 'wb') as f:#DEV_FEATURE_FILE
            pickle.dump(features, f)

    return features

# TODO: 未分段样本转特征
# def convert_examples_to_features(examples, label_list, max_seq_length,
#                                  tokenizer, output_mode, mode,
#                                  cls_token_at_end=False, pad_on_left=False,
#                                  cls_token='[CLS]', sep_token='[SEP]', pad_token=0,
#                                  sequence_a_segment_id=0, sequence_b_segment_id=1,
#                                  cls_token_segment_id=1, pad_token_segment_id=0,
#                                  mask_padding_with_zero=True):
#     """ Loads a data file into a list of `InputBatch`s
#         `cls_token_at_end` define the location of the CLS token:
#             - False (Default, BERT/XLM pattern): [CLS] + A + [SEP] + B + [SEP]
#             - True (XLNet/GPT pattern): A + [SEP] + B + [SEP] + [CLS]
#         `cls_token_segment_id` define the segment id associated to the CLS token (0 for BERT, 2 for XLNet)
#     """
#
#     label_map = {label : i for i, label in enumerate(label_list)}
#
#     features = []
#     for (ex_index, example) in enumerate(examples):
#         if ex_index % 1000 == 0:#10000
#             logger.info("Writing example %d of %d" % (ex_index, len(examples)))
#
#         tokens_a = tokenizer.tokenize(example.text_a)
#
#         tokens_b = None
#         if example.text_b:
#             tokens_b = tokenizer.tokenize(example.text_b)
#             # Modifies `tokens_a` and `tokens_b` in place so that the total
#             # length is less than the specified length.
#             # Account for [CLS], [SEP], [SEP] with "- 3"
#             _truncate_seq_pair(tokens_a, tokens_b, max_seq_length - 3)
#         else:
#             # Account for [CLS] and [SEP] with "- 2"
#             if len(tokens_a) > max_seq_length - 2:
#                 tokens_a = tokens_a[:(max_seq_length - 2)]
#
#         # The convention in BERT is:
#         # (a) For sequence pairs:
#         #  tokens:   [CLS] is this jack ##son ##ville ? [SEP] no it is not . [SEP]
#         #  type_ids:   0   0  0    0    0     0       0   0   1  1  1  1   1   1
#         # (b) For single sequences:
#         #  tokens:   [CLS] the dog is hairy . [SEP]
#         #  type_ids:   0   0   0   0  0     0   0
#         #
#         # Where "type_ids" are used to indicate whether this is the first
#         # sequence or the second sequence. The embedding vectors for `type=0` and
#         # `type=1` were learned during pre-training and are added to the wordpiece
#         # embedding vector (and position vector). This is not *strictly* necessary
#         # since the [SEP] token unambiguously separates the sequences, but it makes
#         # it easier for the model to learn the concept of sequences.
#         #
#         # For classification tasks, the first vector (corresponding to [CLS]) is
#         # used as as the "sentence vector". Note that this only makes sense because
#         # the entire model is fine-tuned.
#         tokens = tokens_a + [sep_token]
#         segment_ids = [sequence_a_segment_id] * len(tokens)
#
#         if tokens_b:
#             tokens += tokens_b + [sep_token]
#             segment_ids += [sequence_b_segment_id] * (len(tokens_b) + 1)
#
#         if cls_token_at_end:
#             tokens = tokens + [cls_token]
#             segment_ids = segment_ids + [cls_token_segment_id]
#         else:
#             tokens = [cls_token] + tokens
#             segment_ids = [cls_token_segment_id] + segment_ids
#
#         input_ids = tokenizer.convert_tokens_to_ids(tokens)
#
#         # The mask has 1 for real tokens and 0 for padding tokens. Only real
#         # tokens are attended to.
#         input_mask = [1 if mask_padding_with_zero else 0] * len(input_ids)
#
#         # Zero-pad up to the sequence length.
#         padding_length = max_seq_length - len(input_ids)
#         if pad_on_left:
#             input_ids = ([pad_token] * padding_length) + input_ids
#             input_mask = ([0 if mask_padding_with_zero else 1] * padding_length) + input_mask
#             segment_ids = ([pad_token_segment_id] * padding_length) + segment_ids
#         else:
#             input_ids = input_ids + ([pad_token] * padding_length)
#             input_mask = input_mask + ([0 if mask_padding_with_zero else 1] * padding_length)
#             segment_ids = segment_ids + ([pad_token_segment_id] * padding_length)
#
#         assert len(input_ids) == max_seq_length
#         assert len(input_mask) == max_seq_length
#         assert len(segment_ids) == max_seq_length
#
#         if output_mode == "classification":
#             label_id = label_map[example.label]
#         elif output_mode == "regression":
#             label_id = float(example.label)
#         else:
#             raise KeyError(output_mode)
#
#         if ex_index < 5:
#             logger.info("*** Example ***")
#             logger.info("guid: %s" % (example.guid))
#             logger.info("tokens: %s" % " ".join(
#                     [str(x) for x in tokens]))
#             logger.info("input_ids: %s" % " ".join([str(x) for x in input_ids]))
#             logger.info("input_mask: %s" % " ".join([str(x) for x in input_mask]))
#             logger.info("segment_ids: %s" % " ".join([str(x) for x in segment_ids]))
#             logger.info("label: %s (id = %d)" % (example.label, label_id))
#
#         features.append(
#                 InputFeatures(input_ids=input_ids,
#                               input_mask=input_mask,
#                               segment_ids=segment_ids,
#                               label_id=label_id))
#     #up_sampling
#
#     if mode == "train":
#         with open(os.path.join(args.data_dir, args.TRAIN_US_FEATURE_FILE), 'wb') as f:#TRAIN_FEATURE_FILE
#             pickle.dump(features, f)
#     else:
#         with open(os.path.join(args.data_dir, args.DEV_US_FEATURE_FILE), 'wb') as f:#DEV_FEATURE_FILE
#             pickle.dump(features, f)
#
#     return features

def preprocess():
    '''
    划分训练集、验证集（上采样）
    :return:
    '''
    datadf = pd.read_csv('./data/Train_DataSet.csv')
    labeldf = pd.read_csv('./data/Train_DataSet_Label.csv')
    #依照id合并
    totaldf = pd.merge(datadf,labeldf, on='id')
    #title,content均包含nan,将title,content二者内容拼接,剔除空行
    totaldf.fillna('', inplace=True)
    totaldf['content'] = totaldf['title'].str.cat(totaldf['content'], sep='-')
    totaldf.drop(['title'],axis=1, inplace=True)
    totaldf.info()
    totaldf = totaldf.dropna(subset=['content'])
    strSeries = totaldf['content'].str.len()
    '''文本长度分布
    count    7265.000000
    mean    1236.930076
    std    1864.796515
    min    8.000000
    25 % 351.000000
    50 % 750.000000
    75 % 1400.000000
    95 % 4547.800000
    max    33773.000000
    Name: content, dtype: float64
    '''
    print(strSeries.describe(percentiles=[.25, .5, .75, .95]))
    '''不同类别样本数量分布，不同类别样本数量不均衡，拟采用上采样生成新样本(Data augmentation)
    1    3590
    2    2914
    0     761
    '''
    print(totaldf['label'].value_counts())
    print(totaldf.isnull().any())

    # X_train, X_dev, y_train, y_dev = train_test_split(
    #     totaldf['content'], totaldf['label'], test_size=0.2, random_state=666)
    # traindf = pd.DataFrame({'content':X_train, 'label':y_train})
    # traindf.to_csv(os.path.join(args.data_dir, args.TRAIN_CORPUS_FILE), sep=',', encoding='utf_8_sig', header=True, index=True)
    # devdf = pd.DataFrame({'content':X_dev, 'label':y_dev})
    # devdf.to_csv(os.path.join(args.data_dir, args.DEV_CORPUS_FILE), sep=',', encoding='utf_8_sig', header=True, index=True)


    # TODO : new added for DA-------------------------------------------------------
    #利用dataframe中的index作为id
    df = pd.DataFrame({'index':range(totaldf.shape[0]), 'content':totaldf['content'], 'label':totaldf['label']})#.set_index('index')
    print(df.head())

    tokens, labels = up_sampling(list(df['index']), list(df['content']), list(df['label']))
    X_train, X_dev, y_train, y_dev = train_test_split(
        tokens, labels, test_size=0.2, random_state=666)

    traindf = pd.DataFrame({'content':X_train, 'label':y_train})
    traindf.to_csv(os.path.join(args.data_dir, args.TRAIN_US_CORPUS_FILE), sep=',', encoding='utf_8_sig', header=True, index=True)
    devdf = pd.DataFrame({'content':X_dev, 'label':y_dev})
    devdf.to_csv(os.path.join(args.data_dir, args.DEV_US_CORPUS_FILE), sep=',', encoding='utf_8_sig', header=True, index=True)
    # test data preprocess
    testdf = pd.read_csv('./data/Test_DataSet.csv')
    # content包含nan,将title,content二者内容拼接,剔除空行
    testdf.fillna('', inplace=True)
    testdf['content'] = testdf['title'].str.cat(testdf['content'], sep='-')
    testdf.drop(['title'], axis=1, inplace=True)
    testdf.info()
    # testdf = pd.DataFrame({'content': testdf['content']})
    testdf.to_csv(os.path.join(args.data_dir, args.TEST_CORPUS_FILE),sep=',', encoding='utf_8_sig', header=True, index=True)
    # TODO : end--------------------------------------------------------------------

if __name__ =='__main__':
    preprocess()