import os
import json
import numpy as np
import logging

log = logging.getLogger("VectorMemory")

class VectorMemory:
    def __init__(self, base_path="data/vector_memory"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
        # Cấu trúc: {namespace: {"vectors": np.array, "metadata": []}}
        self.indices = {}
        self._load_all()

    def _get_paths(self, namespace):
        vec_path = os.path.join(self.base_path, f"{namespace}_vectors.npy")
        meta_path = os.path.join(self.base_path, f"{namespace}_metadata.json")
        return vec_path, meta_path

    def _load_all(self):
        """Load toàn bộ các namespaces có sẵn trong thư mục."""
        for file in os.listdir(self.base_path):
            if file.endswith("_metadata.json"):
                namespace = file.replace("_metadata.json", "")
                self._load_namespace(namespace)

    def _load_namespace(self, namespace):
        vec_path, meta_path = self._get_paths(namespace)
        try:
            if os.path.exists(vec_path) and os.path.exists(meta_path):
                vectors = np.load(vec_path)
                with open(meta_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                self.indices[namespace] = {
                    "vectors": vectors,
                    "metadata": metadata
                }
                log.info(f"Loaded namespace '{namespace}' with {len(metadata)} entries.")
        except Exception as e:
            log.error(f"Error loading namespace {namespace}: {e}")

    def save_namespace(self, namespace):
        if namespace not in self.indices:
            return
        vec_path, meta_path = self._get_paths(namespace)
        try:
            np.save(vec_path, self.indices[namespace]["vectors"])
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(self.indices[namespace]["metadata"], f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"Error saving namespace {namespace}: {e}")

    def add_memory(self, namespace, vector, text, timestamp=None):
        """Thêm một ký ức mới vào namespace."""
        if namespace not in self.indices:
            self.indices[namespace] = {
                "vectors": np.array([vector], dtype=np.float32),
                "metadata": [{"text": text, "timestamp": timestamp}]
            }
        else:
            # Append vector mới
            new_vectors = np.vstack([self.indices[namespace]["vectors"], vector])
            self.indices[namespace]["vectors"] = new_vectors
            self.indices[namespace]["metadata"].append({"text": text, "timestamp": timestamp})
        
        self.save_namespace(namespace)

    def search(self, namespace, query_vector, top_k=3, threshold=0.4):
        """Tìm kiếm các ký ức liên quan nhất."""
        if namespace not in self.indices or len(self.indices[namespace]["metadata"]) == 0:
            return []

        vectors = self.indices[namespace]["vectors"]
        metadata = self.indices[namespace]["metadata"]

        # Tính Cosine Similarity: (A . B) / (||A|| * ||B||)
        # Chuẩn hóa vector truy vấn
        query_vec = np.array(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        
        # Chuẩn hóa tất cả các vectors trong index
        norms = np.linalg.norm(vectors, axis=1)
        
        # Tránh chia cho 0
        norms[norms == 0] = 1e-10
        
        # Dot product
        similarities = np.dot(vectors, query_vec) / (norms * query_norm)
        
        # Lấy top k kết quả có độ tương đồng cao nhất và vượt ngưỡng threshold
        top_indices = np.argsort(similarities)[::-1]
        
        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= threshold:
                results.append({
                    "text": metadata[idx]["text"],
                    "score": score,
                    "timestamp": metadata[idx].get("timestamp")
                })
            if len(results) >= top_k:
                break
        
        return results

# Singleton
vector_memory = None

def get_vector_memory():
    global vector_memory
    if vector_memory is None:
        vector_memory = VectorMemory()
    return vector_memory
