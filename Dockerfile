# 1. Sử dụng môi trường Python 3.12 
FROM python:3.12-slim

# 2. Thiết lập biến môi trường
# Chống ghi file bytecode (.pyc) để nhẹ máy
ENV PYTHONDONTWRITEBYTECODE=1
# Vô hiệu hóa buffer để log hệ thống (print) hiện ra ngay lập tức trên terminal
ENV PYTHONUNBUFFERED=1

# 3. Đặt thư mục làm việc bên trong Container
WORKDIR /app

# 4. Cài đặt các thư viện lõi của hệ điều hành Linux 
# (Bắt buộc phải có gcc và libpq-dev để cài đặt thư viện kết nối PostgreSQL)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy file cấu hình thư viện vào trước để tận dụng bộ nhớ đệm (cache) của Docker
COPY requirements.txt .

# 6. Nâng cấp pip và cài đặt toàn bộ thư viện Python
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
# Cài thêm Gunicorn - Máy chủ web siêu tốc dành cho Production (chạy khỏe hơn manage.py runserver)
RUN pip install gunicorn

# 7. Copy toàn bộ mã nguồn Backend vào trong Container
COPY . .

# 8. Thu thập các file CSS/JS tĩnh của giao diện Admin Django
RUN python manage.py collectstatic --noinput

# 9. Mở cổng 8000 để giao tiếp với bên ngoài
EXPOSE 8000

# 10. Khởi chạy máy chủ Gunicorn
# Đặt timeout=120 giây để hệ thống không bị ngắt kết nối khi đang chạy luồng nạp sách (ETL) nặng
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "config.wsgi:application"]