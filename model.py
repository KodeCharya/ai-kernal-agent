"""Transformer-based log classifier model."""

from __future__ import annotations

from typing import Iterable

try:
    import torch
    from transformers import AutoModel, AutoTokenizer
except ImportError:  # pragma: no cover
    torch = None
    AutoModel = None
    AutoTokenizer = None

from config import LABEL_PROTOTYPES, LABELS, MODEL_NAME, MODEL_TEMPERATURE


class TransformerErrorModel:
    """Classifies cleaned log lines into kernel/system error categories."""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self.labels = list(LABELS)
        self.temperature = MODEL_TEMPERATURE
        self._transformer_ready = torch is not None and AutoModel is not None
        if self._transformer_ready:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            self.model.eval()
            self._prototype_matrix = self._build_prototype_matrix()
        else:
            self._keyword_map = self._build_keyword_map()

    def _encode_texts(self, texts: Iterable[str]) -> torch.Tensor:
        batch = self.tokenizer(
            list(texts),
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=96,
        )
        with torch.no_grad():
            outputs = self.model(**batch).last_hidden_state[:, 0, :]
        return torch.nn.functional.normalize(outputs, p=2, dim=1)

    def _build_prototype_matrix(self) -> torch.Tensor:
        vectors = []
        for label in self.labels:
            examples = LABEL_PROTOTYPES.get(label, [label])
            proto = self._encode_texts(examples).mean(dim=0, keepdim=True)
            vectors.append(torch.nn.functional.normalize(proto, p=2, dim=1))
        return torch.cat(vectors, dim=0)

    def _build_keyword_map(self) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = {}
        for label, samples in LABEL_PROTOTYPES.items():
            bag = " ".join(samples).replace(":", " ").replace(",", " ")
            mapping[label] = {token for token in bag.split() if len(token) > 3}
        return mapping

    def predict(self, text: str) -> tuple[str, float, dict[str, float]]:
        if not self._transformer_ready:
            return self._fallback_predict(text)
        embedding = self._encode_texts([text])
        logits = torch.mm(embedding, self._prototype_matrix.T).squeeze(0)
        probs = torch.softmax(logits / self.temperature, dim=0)
        best_idx = int(torch.argmax(probs).item())
        scores = {label: float(probs[i].item()) for i, label in enumerate(self.labels)}
        return self.labels[best_idx], scores[self.labels[best_idx]], scores

    def _fallback_predict(self, text: str) -> tuple[str, float, dict[str, float]]:
        words = set(text.lower().replace(":", " ").replace(",", " ").split())
        label_scores = {label: 0.0 for label in self.labels}
        for label, terms in self._keyword_map.items():
            if not terms:
                continue
            overlap = len(words & terms) / max(1, len(terms))
            label_scores[label] = overlap
        best = max(label_scores, key=label_scores.get)
        confidence = min(0.99, 0.45 + label_scores[best] * 2.5)
        if label_scores[best] == 0:
            best, confidence = "Unknown", 0.5
        return best, confidence, label_scores
