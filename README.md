# cost-anomaly

Công cụ dòng lệnh phát hiện chi phí AWS tăng bất thường theo từng service, từng ngày.

Tool lấy chi phí 90 ngày gần nhất từ AWS Cost Explorer (DAILY, group theo SERVICE, `UnblendedCost`, chỉ `RECORD_TYPE=Usage`). Mỗi ngày trong khung đánh giá được so với 30 ngày ngay trước nó bằng median + MAD, kết hợp ngưỡng USD tuyệt đối. Kết quả gồm:

- `anomalies.csv`: bảng bất thường.
- `anomalies_report.html`: report có biểu đồ, nhận định và giải thích từng con số. File tự chứa nên mở offline được.
- `anomalies_report.md`: nội dung như HTML nhưng không có biểu đồ, tiện dán vào ticket, wiki hoặc chat.

## Yêu cầu

- [uv](https://docs.astral.sh/uv/getting-started/installation/). uv tự cài Python ≥ 3.11 nếu máy chưa có.
- Một **IAM role** ở account cần phân tích, có quyền `ce:GetCostAndUsage`. Role có quyền rộng hơn (kể cả AdministratorAccess) vẫn dùng được, xem [Bảo mật](#bảo-mật).
- Một **identity nguồn** (IAM user hoặc SSO profile) được phép gọi `sts:AssumeRole` vào role đó. Trust policy của role phải cho phép identity này, và yêu cầu MFA nếu có cấu hình MFA.
- Max session duration của role ≥ `duration_seconds` trong profile (mặc định 3600 giây).

Phạm vi dữ liệu phụ thuộc account chứa role. Ở management account của AWS Organizations, Cost Explorer trả về chi phí gộp của mọi linked account. Ở member account, Cost Explorer chỉ trả về chi phí của chính account đó, và chỉ khi management account cho phép member account truy cập Cost Explorer.

## Cài đặt

Cài bằng `uv tool install`. Lệnh `cost-anomaly` sẽ có trong `PATH`, chạy trong môi trường riêng, không ảnh hưởng Python của máy.

**Từ file wheel** do người quản lý tool phát hành:

```sh
uv tool install ./cost_anomaly-0.1.0-py3-none-any.whl
```

**Từ Git repo nội bộ** (cần quyền đọc repo):

```sh
uv tool install git+ssh://git@<git-host>/<org>/aws-cost-explorer-analysis.git
# hoặc một phiên bản cụ thể:
uv tool install git+ssh://git@<git-host>/<org>/aws-cost-explorer-analysis.git@v0.1.0
```

Cập nhật và gỡ cài đặt:

```sh
uv tool upgrade cost-anomaly   # với bản cài từ Git
uv tool install --force ./cost_anomaly-<phiên-bản-mới>-py3-none-any.whl   # với bản cài từ wheel
uv tool uninstall cost-anomaly
```

Nếu không muốn cài tool, xem phần [Chạy trực tiếp từ mã nguồn](#chạy-trực-tiếp-từ-mã-nguồn-không-cài-tool). Nếu đang phát triển tool, xem phần [Phát triển](#phát-triển).

## Chạy trực tiếp từ mã nguồn (không cài tool)

Tải repo về (`git clone` hoặc file zip), rồi chạy file [`run.py`](run.py) ở thư mục gốc. File này chạy thẳng code trong `src/`, không cài lệnh `cost-anomaly` vào máy. Tool chỉ cần **Python ≥ 3.11** và thư viện **boto3**.

Lưu ý: Python có sẵn trên macOS (`/usr/bin/python3`) là 3.9, không chạy được. Nếu dùng phiên bản quá cũ, `run.py` sẽ báo lỗi kèm phiên bản đang dùng.

**Cách A: có uv** (không cần tự cài Python hay boto3):

```sh
cd aws-cost-explorer-analysis
uv run run.py --profile project-cost
```

Lần đầu, uv tạo thư mục `.venv` ngay trong repo và cài boto3 vào đó. Không có gì được cài ra ngoài repo; xóa thư mục repo là sạch.

**Cách B: chỉ có Python ≥ 3.11 và pip**

```sh
cd aws-cost-explorer-analysis
python3 -m venv .venv                 # tạo môi trường riêng trong repo (chỉ làm lần đầu)
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install boto3                     # chỉ làm lần đầu
python run.py --profile project-cost
```

Những lần chạy sau chỉ cần `source .venv/bin/activate` rồi `python run.py ...`.

`python run.py` nhận đúng các tham số của lệnh `cost-anomaly` và cho cùng kết quả: CSV và report được ghi vào thư mục đang đứng. Trong phần [Hướng dẫn chạy](#hướng-dẫn-chạy) bên dưới, chỉ cần thay `cost-anomaly` bằng `uv run run.py` (cách A) hoặc `python run.py` (cách B). Ví dụ:

```sh
python run.py --profile project-cost --output reports/2026-10-15.csv --k 3
```

## Cấu hình AWS profile

Thêm vào `~/.aws/config` một profile nguồn và một profile switch-role:

```ini
[profile base]
region = us-east-1

[profile project-cost]
source_profile = base
role_arn = arn:aws:iam::<TARGET_ACCOUNT_ID>:role/<ROLE_NAME>
mfa_serial = arn:aws:iam::<SOURCE_ACCOUNT_ID>:mfa/<DEVICE>
# duration_seconds = 3600   # tùy chọn, mặc định 3600
# external_id = ...         # tùy chọn
```

- Credential của profile `base` nằm trong `~/.aws/credentials`, hoặc lấy qua SSO bằng `aws sso login --profile base`.
- `role_arn` và `source_profile` là bắt buộc. Bỏ `mfa_serial` nếu trust policy của role không yêu cầu MFA.
- Tool tự gọi AssumeRole và không dùng cache credential của AWS CLI/boto3. Vì vậy nếu profile có `mfa_serial`, mỗi lần chạy đều phải nhập mã MFA.
- Cost Explorer luôn được gọi ở `us-east-1`, không phụ thuộc `region` của profile.

## Hướng dẫn chạy

### 1. Chạy tool

```sh
cost-anomaly --profile project-cost
# hoặc dùng biến môi trường:
AWS_PROFILE=project-cost cost-anomaly
# không cài tool: uv run run.py --profile project-cost   hoặc   python run.py --profile project-cost
```

Nếu shell đã có sẵn biến `AWS_PROFILE`, chạy không kèm `--profile` sẽ dùng profile đó.

### 2. Nhập mã MFA

```text
Enter MFA code for arn:aws:iam::444455556666:mfa/my-device:
```

Nhập mã 6 số từ thiết bị MFA. Mã không hiện ra khi gõ.

### 3. Xem kết quả

```text
Found 9 anomalies → anomalies.csv
Report → anomalies_report.html, anomalies_report.md
```

Mở `anomalies_report.html` bằng trình duyệt. Nên đọc theo thứ tự:

1. **Nhận định chính**: tổng chi phí 7 ngày đánh giá, phần vượt mức bình thường, service đóng góp nhiều nhất. Phần này cũng cho biết mỗi bất thường là sự kiện một ngày, kéo dài nhiều ngày, hay vẫn còn ở ngày mới nhất.
2. **Bước tiếp theo**: việc cần kiểm tra tương ứng với từng loại bất thường.
3. **Biểu đồ** chi phí 90 ngày của từng service bất thường, có median, vùng bình thường và các điểm bị báo. Rê chuột (hoặc focus rồi dùng ←/→) để xem số liệu từng ngày.
4. **Bảng bất thường**: mỗi dòng kèm giải thích các con số.
5. **Biến động bị lọc**: những ngày có dấu hiệu tăng nhưng không bị báo, kèm lý do. Đọc mục này khi cần chỉnh ngưỡng.
6. **Cấu hình thuật toán** và **Giải thích các cột**.

### Ví dụ khác

```sh
# Ghi kết quả vào thư mục riêng (report nằm cạnh CSV: reports/2026-10-15_report.html ...)
cost-anomaly --profile project-cost --output reports/2026-10-15.csv

# Phân tích lùi về một mốc trong quá khứ (ngày kết thúc không tính vào khung)
cost-anomaly --profile project-cost --end-date 2026-09-30

# Nhạy hơn: z > 3 và chỉ cần tăng $5 là báo
cost-anomaly --profile project-cost --k 3 --min-delta 5

# Chỉ ghi CSV
cost-anomaly --profile project-cost --no-report
```

Thư mục trong `--output` phải tồn tại trước khi chạy.

### Tham số

| Cờ | Mặc định | Ý nghĩa |
|---|---|---|
| `--profile` | `$AWS_PROFILE` | Profile switch-role trong `~/.aws/config` (bắt buộc) |
| `--output` | `anomalies.csv` | File CSV. Report được ghi cạnh file này thành `<tên>_report.html` và `<tên>_report.md` |
| `--k` | `3.5` | Ngưỡng robust z-score. Tăng thì ít cảnh báo hơn |
| `--min-delta` | `10` | Số USD tối thiểu vượt median thì SPIKE mới được báo |
| `--new-threshold` | `10` | USD/ngày tối thiểu để báo NEW_SERVICE |
| `--min-history` | `7` | Số ngày có chi phí > 0 trong baseline cần để dùng z-score. Ít hơn thì service được coi là service mới |
| `--max-pages` | `20` | Số request Cost Explorer tối đa (mỗi request $0.01) |
| `--end-date` | hôm nay (UTC) | Ngày kết thúc khung lấy dữ liệu, dạng `YYYY-MM-DD`, không tính vào khung |
| `--no-report` | | Không ghi report HTML/Markdown |

Mã thoát: `0` khi chạy thành công (kể cả khi có bất thường). `2` khi tham số sai hoặc gặp lỗi xác thực / Cost Explorer; khi đó không ghi file nào.

## Cách phát hiện

Với `--end-date` = T (mặc định là hôm nay):

- Tool lấy dữ liệu các ngày `[T−90, T)`.
- Bỏ qua 2 ngày gần nhất (T−2, T−1) vì Cost Explorer chưa chốt số liệu.
- Đánh giá 7 ngày từ T−9 đến T−3. Mỗi ngày được so với 30 ngày ngay trước nó:

```text
median = trung vị chi phí 30 ngày baseline (ngày không có chi phí tính là $0)
MAD    = trung vị |chi phí − median|
σ̂      = max(1.4826 × MAD, 1% × median, $0.01)
z      = (cost − median) / σ̂

SPIKE        ⇔ baseline có ≥ min_history ngày có chi phí, z > k và cost − median ≥ min_delta
NEW_SERVICE  ⇔ baseline có < min_history ngày có chi phí và cost ≥ new_threshold
```

Median và MAD ít bị ảnh hưởng bởi các đỉnh cũ: một ngày tăng vọt trong quá khứ không kéo ngưỡng lên. Ngưỡng `min_delta` loại các biến động có z cao nhưng số tiền nhỏ.

Lưu ý: một service mới bị gắn NEW_SERVICE **mỗi ngày** cho tới khi baseline của nó có đủ `min_history` ngày có chi phí. Service phát sinh thưa, ví dụ job chạy mỗi tuần một lần, cũng rơi vào trường hợp này. Report có ghi chú riêng cho trường hợp đó.

### Các cột trong CSV

| Cột | Ý nghĩa |
|---|---|
| `date` | Ngày được đánh giá (UTC) |
| `service` | Tên service theo Cost Explorer |
| `kind` | `SPIKE` hoặc `NEW_SERVICE` |
| `cost` | Chi phí trong ngày (USD) |
| `baseline_median` | Median 30 ngày trước, tức mức "bình thường" |
| `mad` | Median Absolute Deviation của 30 ngày đó |
| `robust_z` | Số lần độ dao động thông thường mà chi phí vượt median; để trống với `NEW_SERVICE` |
| `delta` | `cost − baseline_median`, số USD vượt mức bình thường |

Các dòng được sắp theo ngày mới nhất trước, trong cùng ngày thì `delta` lớn trước.

## Bảo mật

Role có thể có quyền rộng, nhưng tool chỉ dùng đúng phần cần thiết:

- Khi gọi `sts:AssumeRole`, tool gửi kèm một **session policy** chỉ cho phép `ce:GetCostAndUsage`. Quyền thực tế là phần giao giữa quyền của role và session policy. Vì vậy credential tạm chỉ đọc được Cost Explorer, kể cả khi bị lộ.
- Trong code, mỗi client có một allowlist API: client STS chỉ gọi được `AssumeRole`, client Cost Explorer chỉ gọi được `GetCostAndUsage`.
- Mỗi lần chạy thường tốn 1–2 request Cost Explorer ($0.01/request). `--max-pages` chặn trường hợp phân trang bất thường.

CSV và report chứa dữ liệu chi phí thật của account. Chỉ chia sẻ cho người có quyền xem chi phí, và không commit lên repo. `.gitignore` đã loại `*.csv`, `*_report.html` và `*_report.md`.

## Xử lý lỗi thường gặp

| Thông báo | Nguyên nhân thường gặp |
|---|---|
| `--profile is required (or set AWS_PROFILE)` | Chưa truyền `--profile` và chưa đặt `AWS_PROFILE` |
| `The config profile (...) could not be found` | Tên profile sai hoặc chưa có trong `~/.aws/config` |
| `profile '...' must define role_arn and source_profile` | Profile thiếu `role_arn` hoặc `source_profile` |
| `AssumeRole failed (AccessDenied): ...` | Trust policy không cho phép identity nguồn, mã MFA sai hoặc hết hạn, hoặc identity nguồn thiếu quyền `sts:AssumeRole` |
| `AssumeRole failed (ValidationError): ... DurationSeconds ...` | `duration_seconds` lớn hơn max session duration của role |
| `GetCostAndUsage failed (AccessDeniedException): ...` | Role không có `ce:GetCostAndUsage`, hoặc member account chưa được management account cho phép dùng Cost Explorer |
| `Stopped after N pages; raise --max-pages if this is expected` | Dữ liệu cần nhiều trang hơn giới hạn; tăng `--max-pages` |

## Demo offline

Cần mã nguồn (repo). Demo chạy CLI thật trên AWS giả lập: file config tạm, MFA giả, STS và Cost Explorer được stub bằng `botocore.stub.Stubber`. Dữ liệu là số liệu tổng hợp có cài sẵn các kịch bản: EC2 tăng đột biến, NAT/data transfer tăng 2 ngày, Bedrock mới xuất hiện, Lambda tăng nhỏ bị lọc. Demo không gọi AWS và không tốn phí.

```sh
uv sync
uv run python demo/run_demo.py --end-date 2026-10-15
```

Kết quả: `demo/demo_anomalies.csv`, `demo/demo_anomalies_report.html`, `demo/demo_anomalies_report.md`.

## Phát triển

```sh
uv sync                                    # cài dependency (gồm pytest)
uv run cost-anomaly --profile project-cost # chạy từ source
uv run pytest -q                           # chạy toàn bộ test
uv run pytest tests/test_detect.py -q      # một file test
uv build                                   # tạo dist/*.whl và dist/*.tar.gz để phát hành
```

Test không gọi AWS thật. Chúng dùng credential giả, file config tạm, và response giả lập bằng `botocore.stub.Stubber` cùng các fixture JSON.

Luồng xử lý chính: `auth` (AssumeRole + session policy) → `guard` (allowlist API) → `fetch` (phân trang) → `transform` (ma trận service × ngày) → `detect` → `report` (CSV) → `analysis` → `html_report` / `md_report`.
