import random
import textwrap
from typing import Any

import evals
import evals.metrics
from evals.prompt.base import is_chat_prompt
from evals.elsuite.diacritization.utils import calculate_diacritization_score


class Diacritization(evals.Eval):
    def __init__(
        self,
        samples_jsonl: str,
        *args,
        max_tokens: int = 500,
        num_few_shot: int = 0,
        few_shot_jsonl: str = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.samples_jsonl = samples_jsonl
        self.max_tokens = max_tokens
        self.num_few_shot = num_few_shot
        self.few_shot_jsonl = few_shot_jsonl
        if self.num_few_shot > 0:
            assert (
                few_shot_jsonl is not None
            ), "few shot requires few shot sample dataset"
            self.few_shot_jsonl = few_shot_jsonl
            self.few_shot = evals.get_jsonl(self.few_shot_jsonl)

    def eval_sample(self, sample: Any, *_):
        prompt = sample["input"]
        expected = sample["ideal"]

        if self.num_few_shot > 0:
            assert is_chat_prompt(sample["input"]), "few shot requires chat prompt"
            prompt = sample["input"][:-1]
            for s in self.few_shot[: self.num_few_shot]:
                prompt += s["sample"]
            prompt += sample["input"][-1:]

        assert isinstance(
            expected, str
        ), "ideal entry in jsonl (i.e. expected) should be string"

        sampled = evals.sample_freeform(
            self.model_spec,
            prompt,
            max_tokens=self.max_tokens,
        )

        if expected is not None:
            (
                der,
                wer,
                der_with_case_ending,
                wer_with_case_ending,
            ) = calculate_diacritization_score(
                predicted=sampled,
                expected=expected,
            )
            evals.record.default_recorder().record_event(
                type="diacritization",
                data=dict(
                    der=der,
                    wer=wer,
                    sampled=sampled,
                    expected=expected,
                    der_with_case_ending=der_with_case_ending,
                    wer_with_case_ending=wer_with_case_ending,
                ),
            )

    def run(self, recorder):
        """
        Called by the `oaieval` CLI to run the eval. The `eval_all_samples` method calls `eval_sample`.
        """
        samples = evals.get_jsonl(self.samples_jsonl)
        self.eval_all_samples(recorder, samples)
        events = recorder.get_events("diacritization")

        ders = list(map(lambda e: e.data["der"], events))
        wers = list(map(lambda e: e.data["wer"], events))
        ders_with_case_ending = list(
            map(lambda e: e.data["der_with_case_ending"], events)
        )
        wers_with_case_ending = list(
            map(lambda e: e.data["wer_with_case_ending"], events)
        )

        get_average = lambda items: sum(items) / len(items)

        average_ders = get_average(ders)
        average_wers = get_average(wers)
        average_ders_with_case_ending = get_average(ders_with_case_ending)
        average_wers_with_case_ending = get_average(wers_with_case_ending)

        return {
            "average_ders": average_ders,
            "average_wers": average_wers,
            "average_ders_with_case_ending": average_ders_with_case_ending,
            "average_wers_with_case_ending": average_wers_with_case_ending,
        }
