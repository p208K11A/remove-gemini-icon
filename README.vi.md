# clean-video: xóa icon Gemini + tăng chất lượng video

[English](README.md)

Xóa icon ngôi sao mà Gemini / Veo chèn ở góc dưới bên phải video 1280x720, rồi xuất file Full HD (hoặc 4K)
chất lượng cao.

Repo đi kèm: **make-video** dựng video hoàn chỉnh (giới thiệu / quảng cáo) từ các clip đã làm sạch.

## Cài đặt

- **ffmpeg** trong PATH (Windows: `winget install Gyan.FFmpeg`)
- **Python 3.10+**, rồi `pip install -r requirements.txt` (numpy, Pillow)
- Tùy chọn, cho `--ai`: `python setup_realesrgan.py` (tải Real-ESRGAN ncnn-vulkan vào `bin/`, chạy trên mọi GPU hỗ trợ Vulkan)

## Một file

```bash
python clean.py input.mp4 output.mp4                    # Lanczos lên 1920x1080 (nhanh, ~bằng thời lượng video)
python clean.py input.mp4 output.mp4 --ai               # AI upscale Real-ESRGAN (nét hơn, chậm hơn nhiều)
python clean.py input.mp4 output.mp4 --size 3840x2160 --sharpen 0
python clean.py input.mp4 output.mp4 --no-watermark     # chỉ upscale, mọi độ phân giải
```

| Tùy chọn | Mặc định | |
|---|---|---|
| `--size WxH` | `1920x1080` | kích thước xuất |
| `--sharpen N` | `0.8` (`0.3` khi `--ai`) | độ làm nét, `0` = tắt, `1.2` = mạnh |
| `--ai` | tắt | upscale bằng Real-ESRGAN (chạy `python setup_realesrgan.py` một lần trước) |
| `--ai-model` | `realesr-animevideov3` | hoặc `realesrgan-x4plus` (tốt hơn với ảnh thật, chậm hơn ~50 lần trên GPU tích hợp) |
| `--crf N` | `16` | chất lượng x264, nhỏ hơn = đẹp hơn, file nặng hơn |
| `--no-watermark` | | bỏ qua bước xóa icon |

Tốc độ đo trên GPU tích hợp Intel UHD 770: Lanczos ~8 giây cho clip 10 giây; `--ai` với animevideov3 ~2.5 giây/frame
(~10 phút cho clip 10 giây). Giới hạn chất lượng: Gemini xuất 720p ~2 Mbps, nên upscale làm sạch và nét hơn
nhưng không tạo ra chi tiết thật.

## Luồng xử lý nhiều file

Thư mục làm việc (mặc định là chính thư mục này, hoặc `--workspace DIR`, hoặc biến môi trường `VIDKIT_WORKSPACE`)
gồm 3 thư mục, tự tạo khi cần và bị git bỏ qua:

```
inqueue/      bỏ video mới vào đây (bản gốc không bao giờ bị sửa)
InProgress/   bản sao đang xử lý + kết quả ({tên}-output.mp4)
Done/         video đã hoàn thành
```

```bash
python process.py --pull          # chép inqueue/* -> InProgress/, xử lý mọi video nguồn
python process.py clip1 --ai      # xử lý lại một clip với tùy chọn khác (ghi đè kết quả)
python done.py --dry-run          # xem trước sẽ làm gì
python done.py                    # InProgress/{tên}-output.mp4 -> Done/{tên}.mp4, dọn sạch InProgress/
```

Video nào trong `InProgress/` có tên không kết thúc bằng `-output` là video nguồn (đuôi `-current` có hay không đều
được, sẽ bị bỏ khỏi tên kết quả). `done.py` không bao giờ ghi đè: tự thêm `_2`, `_3`... Trên Windows: bấm đúp
`process.bat` / `done.bat` (done sẽ hỏi y/N).

## Cách xóa icon hoạt động

Gemini trộn ngôi sao trắng vào khung hình: `hiển_thị = a*255 + (1-a)*gốc`. Với mặt nạ alpha đã hiệu chỉnh
(`gemini_star_alpha_720p.npy`, 112x112 tại x=1104, y=544, alpha đỉnh ~0.30) có thể khôi phục chính xác điểm ảnh gốc:
`gốc = (hiển_thị - a*255) / (1 - a)`. Sau đó làm mềm một dải ~2px dọc viền ngôi sao, vì nén H.264 để lại viền
chấm mờ ở cạnh sắc. Cách này tốt hơn làm mờ/inpaint (bộ lọc `delogo` của ffmpeg để lại vết nhòe trên nền có họa tiết).

**Độ phân giải khác** cần mặt nạ mới. Gom các clip có ngôi sao nằm trên vùng tối, phẳng, rồi chạy:

```bash
python calibrate_mask.py new_mask.npy clip1.mp4 clip2.mp4 ...
```

và chỉnh `OX, OY, MASK_FRAME` trong `clean.py`. Luôn kiểm tra ảnh phóng to góc video ở nhiều cảnh.

## Giấy phép

MIT. Real-ESRGAN (tải riêng): BSD-3-Clause. Đảm bảo bạn có quyền với các video đưa vào xử lý.
