# Hướng dẫn đóng góp

## Quy trình

### 1. Fork & Clone

```bash
git clone https://github.com/<your-username>/micro-positioning-system.git
cd micro-positioning-system
git remote add upstream https://github.com/<original-owner>/micro-positioning-system.git
```

### 2. Tạo nhánh

```bash
git checkout -b feat/ten-tinh-nang
# hoặc
git checkout -b fix/ten-bug
```

### 3. Cài đặt môi trường dev

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

### 4. Phát triển

Chạy tests trước và sau khi chỉnh sửa:

```bash
python -m pytest tests/ -v
```

### 5. Commit

```
<type>(<scope>): <mô tả ngắn>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

Ví dụ:
```
feat(vision): thêm CLAHE adaptive histogram equalization
fix(ransac): sửa edge case khi extent_range lọc hết cạnh
docs(api): cập nhật SerialSender.update signature
```

### 6. Pull Request

```bash
git push origin feat/ten-tinh-nang
```

Điền đầy đủ PULL_REQUEST_TEMPLATE.

---

## Coding style

- Python 3.10+ (dùng `X | Y`, `match`, `slots=True`, ...)
- Type hints đầy đủ cho hàm public
- Docstring kiểu Google
- Tên: `snake_case` (hàm/biến), `PascalCase` (class), `UPPER_CASE` (hằng)
- Không dùng `from X import *`

---

## Thêm block mới vào `vision_pipeline.py`

1. Đặt block theo thứ tự số (Block N)
2. Giải thích tối ưu hoá so với phiên bản trước (nếu có)
3. Thêm unit test vào `tests/test_vision.py`
4. Cập nhật `docs/api.md` và `docs/methodology.md`
5. Ghi vào `CHANGELOG.md`

---

## Báo cáo lỗi / Đề xuất tính năng

Mở Issue và dùng template trong `.github/ISSUE_TEMPLATE/`.
