import asyncio
from dataclasses import dataclass

import numpy as np
from faster_whisper import WhisperModel
from loguru import logger
from .asr_interface import ASRInterface


@dataclass(frozen=True)
class RecognitionResult:
    text: str
    uncertain: bool = False


class VoiceRecognition(ASRInterface):
    BEAM_SEARCH = True
    # SAMPLE_RATE # Defined in asr_interface.py

    def __init__(
        self,
        model_path: str = "distil-medium.en",
        download_root: str = None,
        language: str = "en",
        device: str = "auto",
        compute_type: str = "int8",
        prompt: str = None,
        cpu_threads: int = 4,
    ) -> None:
        self.MODEL_PATH = model_path
        self.LANG = language
        self.prompt = prompt
        self.model = WhisperModel(
            model_size_or_path=model_path,
            download_root=download_root,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
        )

    def transcribe_np(self, audio: np.ndarray) -> str:
        return self.transcribe_with_details(audio).text

    async def async_transcribe_with_details(
        self, audio: np.ndarray
    ) -> RecognitionResult:
        # Return per-utterance data, rather than shared mutable confidence state.
        return await asyncio.to_thread(self.transcribe_with_details, audio)

    def transcribe_with_details(self, audio: np.ndarray) -> RecognitionResult:
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        if (
            audio.size < self.SAMPLE_RATE * 0.15
            or not np.all(np.isfinite(audio))
            or np.max(np.abs(audio)) < 1e-5
        ):
            return RecognitionResult("")
        segments, _ = self.model.transcribe(
            audio,
            task="transcribe",
            beam_size=5 if self.BEAM_SEARCH else 1,
            temperature=0,
            language=self.LANG or None,
            condition_on_previous_text=False,
            initial_prompt=self.prompt,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,
        )
        segments = [segment for segment in segments if segment.text.strip()]
        text = " ".join(segment.text.strip() for segment in segments)
        if not segments:
            return RecognitionResult("")
        durations = [max(segment.end - segment.start, 0.01) for segment in segments]
        confidence = sum(
            segment.avg_logprob * duration
            for segment, duration in zip(segments, durations)
        ) / sum(durations)
        uncertain = confidence < -0.85 or any(
            segment.avg_logprob < -1.2
            or segment.compression_ratio > 2.4
            or (segment.no_speech_prob > 0.6 and segment.avg_logprob < -0.5)
            for segment in segments
        )
        logger.info(
            "ASR model={} language={} duration={:.1f}s logprob={:.2f} uncertain={}",
            self.MODEL_PATH,
            self.LANG,
            audio.size / self.SAMPLE_RATE,
            confidence,
            uncertain,
        )
        return RecognitionResult(text, uncertain)
