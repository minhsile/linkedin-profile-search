FROM postgres:16
# tzdata-legacy cung cấp các alias timezone cũ (vd Asia/Saigon) mà một số client JDBC
# (DBeaver trên máy locale VN) gửi khi handshake — nếu thiếu sẽ lỗi FATAL invalid TimeZone.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata-legacy \
    && rm -rf /var/lib/apt/lists/*
