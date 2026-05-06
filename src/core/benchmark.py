import time
import threading
import pynvml
import matplotlib.pyplot as plt
import os
from datetime import datetime

class AIBenchmark:
    def __init__(self):
        self.gpu_usage = []
        self.timestamps = []
        self.is_running = False
        self.start_time = None
        self.end_time = None
        self.sampling_thread = None
        self.has_gpu = False
        
        try:
            pynvml.nvmlInit()
            # Lấy handle cho GPU đầu tiên
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.gpu_name = pynvml.nvmlDeviceGetName(self.handle)
            self.has_gpu = True
        except Exception as e:
            print(f"NVML Initialization failed: {e}")
            self.gpu_name = "N/A"

    def _sample_gpu(self):
        """Hàm chạy ngầm để lấy mẫu GPU."""
        while self.is_running:
            if self.has_gpu:
                try:
                    util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
                    self.gpu_usage.append(util.gpu)
                    self.timestamps.append(time.time() - self.start_time)
                except Exception:
                    pass
            time.sleep(0.2) # Lấy mẫu mỗi 200ms để biểu đồ mượt hơn

    def start(self):
        """Bắt đầu đo đạc."""
        self.gpu_usage = []
        self.timestamps = []
        self.start_time = time.time()
        self.is_running = True
        self.sampling_thread = threading.Thread(target=self._sample_gpu, daemon=True)
        self.sampling_thread.start()

    def stop(self):
        """Dừng đo đạc và trả về kết quả tổng hợp."""
        self.is_running = False
        if self.sampling_thread:
            self.sampling_thread.join(timeout=1.0)
        self.end_time = time.time()
        
        duration = self.end_time - self.start_time
        avg_gpu = sum(self.gpu_usage) / len(self.gpu_usage) if self.gpu_usage else 0
        peak_gpu = max(self.gpu_usage) if self.gpu_usage else 0
        
        return {
            "duration": duration,
            "avg_gpu": avg_gpu,
            "peak_gpu": peak_gpu,
            "gpu_name": self.gpu_name
        }

    def generate_chart(self, filename="data/benchmarks/last_run.png"):
        """Tạo biểu đồ GPU và lưu vào file."""
        if not self.gpu_usage:
            return None
            
        # Sử dụng style hiện đại
        plt.style.use('dark_background')
        plt.figure(figsize=(8, 4))
        
        # Vẽ dữ liệu
        plt.plot(self.timestamps, self.gpu_usage, color='#00ffcc', linewidth=2, label='GPU Load')
        plt.fill_between(self.timestamps, self.gpu_usage, color='#00ffcc', alpha=0.1)
        
        # Cấu hình trục và tiêu đề
        plt.title(f'AI Performance Benchmark - {self.gpu_name}', pad=15, color='white', fontweight='bold')
        plt.xlabel('Time (seconds)', color='gray')
        plt.ylabel('Utilization (%)', color='gray')
        plt.ylim(0, 100)
        plt.grid(True, linestyle=':', alpha=0.3)
        
        # Hiển thị số giây tổng cộng
        if self.timestamps:
            plt.text(self.timestamps[-1], self.gpu_usage[-1], f' {self.gpu_usage[-1]}%', color='#00ffcc', va='center')

        plt.tight_layout()
        
        # Lưu file
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        plt.savefig(filename, transparent=False, facecolor='#1a1a1a')
        plt.close()
        return filename
