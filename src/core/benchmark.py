import time
import threading
import pynvml
import matplotlib.pyplot as plt
import os
import subprocess
from datetime import datetime
from src.core.logger import log

class AIBenchmark:
    _nvml_initialized = False

    def __init__(self):
        self.gpu_usage = []
        self.timestamps = []
        self.is_running = False
        self.start_time = None
        self.end_time = None
        self.sampling_thread = None
        self.has_gpu = False
        self.gpu_name = "N/A"
        self.error_msg = None
        
        try:
            if not AIBenchmark._nvml_initialized:
                pynvml.nvmlInit()
                AIBenchmark._nvml_initialized = True
            
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                # Tìm GPU có utilization cao nhất hoặc mặc định là cái đầu tiên
                # Ở đây ta lấy cái đầu tiên có nhãn NVIDIA
                self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(self.handle)
                self.gpu_name = name.decode('utf-8') if isinstance(name, bytes) else str(name)
                self.has_gpu = True
            else:
                self.error_msg = "No NVIDIA GPUs found."
        except Exception as e:
            self.error_msg = str(e)
            log.error(f"NVML Init Error: {e}")
            # Thử kiểm tra qua nvidia-smi CLI như phương án dự phòng
            try:
                out = subprocess.check_output(['nvidia-smi', '-L'], encoding='utf-8')
                if out:
                    self.gpu_name = out.split('\n')[0].split('(')[0].strip()
                    # Nếu có nvidia-smi, ta vẫn có thể lấy mẫu qua CLI
                    self.has_gpu = True 
                    self.use_smi_cli = True
                    log.info(f"Fallback to nvidia-smi: {self.gpu_name}")
                else:
                    self.has_gpu = False
            except:
                self.has_gpu = False

    def _get_gpu_util(self):
        """Lấy phần trăm sử dụng GPU hiện tại."""
        try:
            if hasattr(self, 'use_smi_cli') and self.use_smi_cli:
                out = subprocess.check_output(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], encoding='utf-8')
                return float(out.strip())
            else:
                util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
                return float(util.gpu)
        except:
            return 0.0

    def _sample_gpu(self):
        """Hàm chạy ngầm để lấy mẫu GPU."""
        while self.is_running:
            if self.has_gpu:
                self.gpu_usage.append(self._get_gpu_util())
                self.timestamps.append(time.time() - self.start_time)
            time.sleep(0.3)

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
