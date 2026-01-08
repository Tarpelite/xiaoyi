"""
Embedding 服务模块
==================

使用 BGE-M3 生成稠密和稀疏向量
"""

from typing import List, Dict, Tuple, Optional
from FlagEmbedding import BGEM3FlagModel
import numpy as np
import time
import torch


class EmbeddingService:
    """BGE-M3 Embedding 服务"""

    _instance: Optional["EmbeddingService"] = None
    _model: Optional[BGEM3FlagModel] = None

    def __new__(cls, model_name: str = "BAAI/bge-m3"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        if EmbeddingService._model is None:
            # Determine device and FP16 support
            if torch.cuda.is_available():
                device = "cuda:0"
                use_fp16 = True
            elif torch.backends.mps.is_available():
                device = "mps"
                use_fp16 = False  # MPS doesn't fully support FP16
            else:
                device = "cpu"
                use_fp16 = False

            print(f"Loading BGE-M3 model: {model_name} (device={device}, fp16={use_fp16})")
            EmbeddingService._model = BGEM3FlagModel(
                model_name,
                use_fp16=use_fp16,
                device=device
            )
            print("BGE-M3 model loaded successfully")

    @property
    def model(self) -> BGEM3FlagModel:
        return EmbeddingService._model

    def encode(
        self,
        texts: List[str],
        batch_size: int = 12,
        max_length: int = 512
    ) -> Dict[str, np.ndarray]:
        """
        编码文本，返回稠密和稀疏向量

        Args:
            texts: 文本列表
            batch_size: 批大小
            max_length: 最大长度

        Returns:
            {
                "dense": np.ndarray,  # (n, 1024)
                "sparse": List[Dict]  # [{indices, values}, ...]
            }
        """
        print(f"[Embed] 编码 {len(texts)} 个文本块...")
        start_time = time.time()

        output = self.model.encode(
            texts,
            batch_size=batch_size,
            max_length=max_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False
        )

        elapsed = time.time() - start_time
        print(f"[Embed] 完成, 耗时: {elapsed:.2f}s")

        return {
            "dense": output["dense_vecs"],
            "sparse": self._convert_sparse(output["lexical_weights"])
        }

    def encode_query(self, query: str) -> Dict[str, any]:
        """编码查询文本"""
        result = self.encode([query])
        return {
            "dense": result["dense"][0],
            "sparse": result["sparse"][0]
        }

    def _convert_sparse(self, lexical_weights: List[Dict]) -> List[Dict]:
        """
        转换稀疏向量格式为 Qdrant 兼容格式

        Returns:
            [{indices: [...], values: [...]}, ...]
        """
        sparse_vectors = []
        for weights in lexical_weights:
            indices = list(weights.keys())
            values = list(weights.values())
            sparse_vectors.append({
                "indices": indices,
                "values": values
            })
        return sparse_vectors
