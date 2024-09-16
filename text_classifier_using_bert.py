# -*- coding: utf-8 -*-
"""Text Classifier using BERT.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1D6npwl4K2AGPSbQKSF8TuCy4jzXWpGSN
"""

!pip install  transformers datasets accelerate evaluate

"""Configuration"""

import torch

class Config:
    DATASET_ID = "emad12/stock_tweets_sentiment"
    MODEL_CKPT = "distilbert-base-uncased"
    SRC_COLUMN = "tweet"
    TGT_COLUMN = "sentiment"
    TEST_SIZE = 0.2
    SEED = 0
    MAX_LEN = 32
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    ID2LABEL = {0: "NEUTRAL", 1: "POSITIVE", 2:"NEGATIVE"}
    LABEL2ID = {"NEUTRAL": 0, "POSITIVE": 1, "NEGATIVE": 2}
    EVAL_METRIC = "accuracy"
    MODEL_OUT_DIR = "distilbert-stock-tweet-sentiment-analysis"
    NUM_EPOCHS = 3
    LR = 2E-5
    BATCH_SIZE = 16
    WEIGHT_DECAY = 0.01
    EVAL_STRATEGY = "epoch"
    SAVE_STRATEGY = "epoch"
    LOGGING_STRATEGY = "epoch"
    PUSH_TO_HUB = True

config = Config()

"""Dataset"""

from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from datasets import Dataset, load_dataset
import pandas as pd
from sklearn.model_selection import train_test_split
import torch
# import config

class TextClassificationDataset:
    def __init__(self):
        self.dataset_id = config.DATASET_ID
        self.model_ckpt = config.MODEL_CKPT
        self.src_column = config.SRC_COLUMN
        self.tgt_column = config.TGT_COLUMN
        self.test_size = config.TEST_SIZE
        self.seed = config.SEED
        self.max_len = config.MAX_LEN
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_ckpt)

    def create_data(self):
        self.data = load_dataset(self.dataset_id, split="train") # load_dataset("parquet", data_files=file_path)
        self.df = self.data.to_pandas()
        self.df = self.df[[self.src_column, self.tgt_column]]
        self.df[self.src_column] = self.df[self.src_column].apply(lambda x: x.lower()) # If needed
        self.df[self.tgt_column] = self.df[self.tgt_column].apply(lambda x: 2 if x==-1 else x) # If needed
        self.df = self.df.sample(20000) # If needed
        self.train_df, self.test_df = train_test_split(self.df, test_size=self.test_size, shuffle=True, random_state=self.seed, stratify=self.df[self.tgt_column])
        self.train_data = Dataset.from_pandas(self.train_df)
        self.test_data = Dataset.from_pandas(self.test_df)
        return self.train_data, self.test_data

    def tokenize_function(self, example):
        model_inp = self.tokenizer(example[self.src_column], truncation=True, padding=True, max_length=self.max_len)
        labels = torch.tensor(example[self.tgt_column], dtype=torch.int)
        model_inp["labels"] = labels
        return model_inp

    def preprocess_function(self, data):
        model_inp = data.map(self.tokenize_function, batched=True, remove_columns=data.column_names)
        return model_inp

    def gen_classification_dataset(self):
        train_data, test_data = self.create_data()
        train_tokenized_data = self.preprocess_function(train_data)
        test_tokenized_data = self.preprocess_function(test_data)
        return train_tokenized_data, test_tokenized_data

"""Model"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments, DataCollatorWithPadding
import evaluate
import numpy as np

class TextClassificationModelTrainer:
    def __init__(self, train_data, test_data):
        self.train_data = train_data
        self.test_data = test_data
        self.model_ckpt = config.MODEL_CKPT
        self.id2label = config.ID2LABEL
        self.label2id = config.LABEL2ID
        self.num_labels = len(self.id2label)
        self.device = config.DEVICE
        self.eval_metric = config.EVAL_METRIC
        self.model_out_dir = config.MODEL_OUT_DIR
        self.num_epochs = config.NUM_EPOCHS
        self.lr = config.LR
        self.batch_size = config.BATCH_SIZE
        self.weight_decay = config.WEIGHT_DECAY
        self.eval_strategy = config.EVAL_STRATEGY
        self.save_strategy = config.SAVE_STRATEGY
        self.logging_strategy = config.LOGGING_STRATEGY
        self.push_to_hub = config.PUSH_TO_HUB
        self.model = AutoModelForSequenceClassification.from_pretrained(
                                                                        self.model_ckpt,
                                                                        id2label=self.id2label,
                                                                        label2id=self.label2id,
                                                                        num_labels=self.num_labels
                                                                        ).to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_ckpt)
        self.eval_metric_computer = evaluate.load(self.eval_metric)
        self.data_collator = DataCollatorWithPadding(self.tokenizer)

    def compute_metrics(self, eval_pred):
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)
        return self.eval_metric_computer.compute(predictions=predictions, references=labels)

    def set_training_args(self):
        return TrainingArguments(
        output_dir = self.model_out_dir,
        num_train_epochs=self.num_epochs,
        learning_rate = self.lr,
        per_device_train_batch_size = self.batch_size,
        per_device_eval_batch_size = self.batch_size,
        weight_decay = self.weight_decay,
        evaluation_strategy = self.eval_strategy,
        save_strategy = self.save_strategy,
        logging_strategy = self.logging_strategy,
        push_to_hub = self.push_to_hub
        )

    def model_trainer(self):
        return Trainer(
            model = self.model,
            args = self.set_training_args(),
            data_collator = self.data_collator,
            train_dataset = self.train_data,
            eval_dataset = self.test_data,
            compute_metrics = self.compute_metrics
        )

    def train_and_save_and_push_to_hub(self):
        trainer = self.model_trainer()
        trainer.train()
        trainer.push_to_hub()

"""Higging Face Login"""

from huggingface_hub import login

login(token="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")

"""Execution"""

if __name__ == "__main__":
    textclassificationdataset = TextClassificationDataset()
    train_data, test_data = textclassificationdataset.gen_classification_dataset()
    textclassificationtrainer = TextClassificationModelTrainer(train_data, test_data)
    textclassificationtrainer.train_and_save_and_push_to_hub()

"""Inference"""

from transformers import pipeline
classifier = pipeline("sentiment-analysis", model=config.MODEL_OUT_DIR, tokenizer="distilbert-base-uncased")
classifier("have a great weekend everyone will be back to full schedule next week spy aapl baba")

