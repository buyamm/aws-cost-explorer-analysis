# cost-anomaly

Công cụ dòng lệnh phát hiện chi phí AWS tăng bất thường theo từng service, từng ngày.

Tool lấy chi phí 90 ngày gần nhất từ AWS Cost Explorer (DAILY, group theo SERVICE, hai metric `UnblendedCost` và `NetAmortizedCost`, gồm usage thường lẫn phần được Savings Plans/RI che). Mỗi ngày trong khung đánh giá được so với 30 ngày ngay trước nó bằng median + MAD, kết hợp ngưỡng USD tuyệt đối. Kết quả gồm:

- `anomalies.csv`: bảng bất thường.
- `anomalies_report.html`: report có biểu đồ, nhận định và giải thích từng con số. File tự chứa nên mở offline được.
- `anomalies_report.md`: nội dung như HTML nhưng không có biểu đồ, tiện dán vào ticket, wiki hoặc chat.
- `anomalies_report.pdf` (khi chạy với `--pdf`): bản in của report HTML, để gửi cho người không mở file HTML.

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

Mở `anomalies_report.html` bằng trình duyệt. Đầu trang là một câu tóm tắt kết quả (số bất thường, số service, số tiền chi thêm) và các con số chính. Thanh trên cùng luôn hiện khi cuộn trang, gồm:

- **Mục lục**: bấm để nhảy tới từng phần.
- **Giao diện tối**: bật/tắt theme tối. Lần đầu mở, report theo cài đặt sáng/tối của hệ điều hành; sau khi chọn, trình duyệt nhớ lựa chọn cho các lần mở sau.
- **Xuất PDF**: mở hộp thoại in của trình duyệt, chọn "Lưu dưới dạng PDF". Bản in luôn dùng theme sáng, ẩn các nút và bộ lọc, in đủ mọi dòng của bảng (kể cả dòng đang bị lọc) theo thứ tự mặc định, và không cắt dòng hay biểu đồ giữa hai trang.

Nên đọc theo thứ tự:

1. **Nhận định chính**: tổng chi phí các ngày đánh giá (mặc định 7, đổi bằng `--eval-days`), phần vượt mức bình thường, service đóng góp nhiều nhất. Phần này cũng cho biết mỗi bất thường là sự kiện một ngày, kéo dài nhiều ngày, hay vẫn còn ở ngày mới nhất.
2. **Bước tiếp theo**: việc cần kiểm tra tương ứng với từng loại bất thường.
3. **Biểu đồ** chi phí 90 ngày của từng service bất thường, có median, vùng bình thường và các điểm bị báo. Rê chuột (hoặc focus rồi dùng ←/→) để xem số liệu từng ngày.
4. **Bảng bất thường**: mỗi dòng kèm giải thích các con số. Có thể lọc theo loại (SPIKE/NEW_SERVICE/DROP), theo service, theo nhãn "tạm tính"/"đã biết", và bấm tiêu đề cột để sắp xếp. "Xóa lọc" đưa bảng về như ban đầu.
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

# Đánh giá 30 ngày thay vì 7 (vẫn chỉ tốn 1–2 request vì dữ liệu lấy về vẫn là 90 ngày)
cost-anomaly --profile project-cost --eval-days 30

# Chỉ ghi CSV
cost-anomaly --profile project-cost --no-report

# Ghi thêm anomalies_report.pdf (cần Chrome, Chromium hoặc Edge trên máy)
cost-anomaly --profile project-cost --pdf
```

`--pdf` dùng trình duyệt có sẵn trên máy ở chế độ headless để in report HTML, nên không cần cài thêm thư viện Python. Tool tìm trình duyệt theo thứ tự: biến môi trường `COST_ANOMALY_BROWSER` (đường dẫn tới file chạy), các lệnh `google-chrome`, `chromium`, `microsoft-edge` trong `PATH`, rồi Chrome/Chromium/Edge trong `/Applications` trên macOS. Nếu không tìm thấy, tool dừng với mã 2 trước khi hỏi MFA. Lambda không tạo PDF.

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
| `--eval-days` | `7` | Số ngày **đã chốt** được đánh giá, từ 1 đến 58 (để mọi ngày đánh giá đều có đủ 30 ngày baseline trong 90 ngày dữ liệu) |
| `--max-pages` | `20` | Số request Cost Explorer tối đa (mỗi request $0.01) |
| `--config` | | File TOML: ngưỡng mặc định, ngưỡng riêng từng service, danh sách `ignore`/`known`. Xem [File config](#file-config) |
| `--with-cad` | | Lấy thêm anomaly của AWS Cost Anomaly Detection để đối chiếu. Xem [Đối chiếu với AWS CAD](#đối-chiếu-với-aws-cad) |
| `--state` | | File JSON lưu các sự cố đã báo. Xem [Sự cố và cảnh báo Slack](#sự-cố-và-cảnh-báo-slack) |
| `--fail-on-anomaly` | | Trả mã 1 khi có điều mới cần xem (dùng cho CI/cron) |
| `--alert-dry-run` | | In nội dung tin nhắn Slack thay vì gửi; không ghi `--state` |
| `--no-drop` | | Không báo DROP (service rơi về gần 0) |
| `--no-provisional` | | Không đánh giá 2 ngày gần nhất (chưa chốt số liệu), quay về khung cũ T−9…T−3 |
| `--end-date` | hôm nay (UTC) | Ngày kết thúc khung lấy dữ liệu, dạng `YYYY-MM-DD`, không tính vào khung |
| `--no-report` | | Không ghi report HTML/Markdown |
| `--pdf` | | Ghi thêm `<tên>_report.pdf` cạnh CSV. Không dùng chung với `--no-report` |

Mã thoát:

| Mã | Ý nghĩa |
|---|---|
| `0` | Chạy thành công (kể cả khi có bất thường, nếu không dùng `--fail-on-anomaly`) |
| `1` | Có `--fail-on-anomaly` và có sự cố mới/xấu đi (khi có `--state`), hoặc có bất thường ở service không thuộc `known` (khi không có `--state`) |
| `2` | Tham số, file config, file state hoặc webhook sai, hoặc lỗi xác thực / Cost Explorer; không ghi CSV. Lỗi cục bộ được phát hiện trước khi hỏi MFA nên không tốn request nào |
| `2` (khi có `--pdf`) | Không tìm thấy trình duyệt (báo trước khi hỏi MFA), hoặc in PDF thất bại. Khi in thất bại, CSV/HTML/Markdown vẫn được ghi và cảnh báo Slack vẫn được gửi |
| `3` | Gửi Slack thất bại sau 3 lần thử. CSV/report vẫn được ghi, state giữ nguyên để lần chạy sau gửi lại |

### File config

Mỗi service có mức dao động và giá trị tiền khác nhau, nên một ngưỡng chung thường quá nhạy với service này và quá lỏng với service khác. File TOML cho phép chỉnh riêng:

```toml
# Key cấp cao nhất phải đặt trước bảng [..] đầu tiên
ignore = ["Tax"]                 # không phân tích
known = ["Amazon Bedrock"]       # vẫn báo, gắn nhãn "đã biết"

[defaults]                       # ghi đè ngưỡng cho mọi service
k = 3.5
min_delta = 10

[services."Amazon Bedrock"]      # tên đúng như dimension SERVICE của Cost Explorer
min_delta = 50
new_threshold = 50

[services."Amazon Relational Database Service"]
min_delta = 5
```

- Key dùng được trong `[defaults]`: `k`, `min_delta`, `new_threshold`, `min_history`, `drop_ratio`, `drop_min_median`, `driver_tolerance`. Trong `[services."…"]`: như trên, trừ `driver_tolerance`.
- Thứ tự ưu tiên: mặc định của tool → `[defaults]` → cờ CLI truyền tường minh → `[services."…"]` của service đó.
- Giá trị phải là số dương, `min_history` là số nguyên, `drop_ratio` nhỏ hơn 1. Key lạ hoặc sai kiểu thì tool dừng với mã 2.
- Ví dụ đầy đủ: `demo/cost-anomaly.toml`.

## Sự cố và cảnh báo Slack

Khi chạy hằng ngày, các khung đánh giá chồng lên nhau (7 ngày đã chốt + 2 ngày tạm tính). Vì vậy cùng một spike xuất hiện ở nhiều lần chạy liên tiếp, và service mới bị gắn NEW_SERVICE mỗi ngày trong một tuần. `--state` giải quyết việc này:

- Các ngày bất thường liên tiếp của cùng service và cùng loại được gộp thành một **sự cố** có ngày bắt đầu/kết thúc.
- Sự cố chỉ được báo khi **mới**, hoặc khi **xấu đi**: đỉnh tăng ít nhất 50% và ít nhất `min_delta` của service so với lần báo trước. DROP so theo độ lớn.
- Service thuộc `known` được ghi nhận nhưng không bao giờ được báo.
- Sự cố đã kết thúc trước khung dữ liệu 90 ngày được xóa khỏi file.
- File state chỉ được ghi sau khi gửi thành công, nên gửi lỗi thì lần sau gửi lại, không mất cảnh báo. File hỏng thì tool dừng với mã 2, không tự xóa (xóa sẽ gửi lại mọi thứ).

### Gửi Slack

1. Trong Slack, tạo app và bật **Incoming Webhooks** cho kênh nhận cảnh báo, rồi copy URL dạng `https://hooks.slack.com/services/...`.
2. Đặt URL vào biến môi trường (không truyền qua tham số, vì tham số lộ trong `ps` và lịch sử shell):

```sh
export COST_ANOMALY_SLACK_WEBHOOK='https://hooks.slack.com/services/...'
cost-anomaly --profile project-cost --state ~/.cost-anomaly/state.json
```

Mỗi lần chạy có sự cố mới/xấu đi sẽ gửi đúng một tin nhắn tiếng Việt. Tin nhắn liệt kê tối đa 10 sự cố, xếp theo tác động tháng, kèm nhãn tạm tính / do giá/coverage và vị trí report. Tool chỉ chấp nhận URL `https://hooks.slack.com/...` và không bao giờ in URL ra. Có thể dùng `--alert-dry-run` để xem trước nội dung.

Không đặt webhook thì danh sách sự cố mới được in ra màn hình. Kết hợp `--fail-on-anomaly` để CI hoặc cron báo lỗi khi có điều mới.

Lưu ý: chạy tay vẫn cần nhập MFA. Để chạy tự động hằng ngày không cần người, xem [Chạy tự động trên AWS Lambda](#chạy-tự-động-trên-aws-lambda).

## Đối chiếu với AWS CAD

AWS Cost Anomaly Detection (CAD) miễn phí và dùng mô hình ML, nhưng là hộp đen. `--with-cad` lấy anomaly của CAD trong cùng khung đánh giá và đặt cạnh kết quả của tool:

- Cột CSV `cad_match`: `true` nếu CAD có anomaly chứa đúng service và ngày đó (theo root cause), `false` nếu chỉ tool thấy, để trống nếu không đối chiếu.
- Report có mục **Đối chiếu AWS CAD**: số dòng cả hai cùng thấy, chỉ tool thấy, và bảng các anomaly chỉ CAD thấy.
- Tin nhắn Slack ghi "AWS CAD cũng phát hiện" khi có.
- Cần bật CAD trong account (có monitor) và role phải có quyền `ce:GetAnomalies`. Nếu không lấy được, tool in cảnh báo rồi chạy tiếp như bình thường.

Lưu ý chi phí: tài liệu AWS không nói rõ `GetAnomalies` có bị tính $0.01/request như `GetCostAndUsage` hay không (thường chỉ 1 request mỗi lần chạy). Cách kiểm tra: chạy thử một lần rồi xem dòng Cost Explorer API trong Bills hôm sau. Vì vậy tính năng này mặc định tắt.

## Chạy tự động trên AWS Lambda

`infra/terraform/` triển khai tool vào chính account cần theo dõi: một Lambda chạy hằng ngày bằng EventBridge Scheduler (mặc định 02:00 UTC = 09:00 giờ Việt Nam). Lambda dùng quyền của execution role nên không cần MFA. Lambda lưu state và report vào S3, đọc webhook Slack từ SSM SecureString.

Thành phần:

| Tài nguyên | Ghi chú |
|---|---|
| Lambda `cost-anomaly` (python3.12) | Code đóng gói từ `src/`, boto3 có sẵn trong runtime. Chỉ chạy 1 lần tại một thời điểm, không tự retry |
| IAM role của Lambda | Chỉ `ce:GetCostAndUsage` (+`ce:GetAnomalies` nếu `with_cad`), `s3:GetObject`/`PutObject` trên `state/incidents.json` và `reports/*`, `ssm:GetParameter` trên đúng parameter webhook, ghi log vào log group của nó. Trong code, mọi client vẫn có allowlist API |
| S3 bucket `<name_prefix>-<account>-<region>` | Chặn public, bắt buộc TLS, mã hóa, versioning; report hết hạn sau `report_retention_days` (90) ngày, bản cũ của state sau 30 ngày |
| EventBridge Scheduler | Không retry, vì mỗi lần chạy lại tốn thêm request Cost Explorer. Ngày lỗi sẽ được lần chạy hôm sau bù lại |
| CloudWatch Logs | Giữ `log_retention_days` (30) ngày |

Các bước (tự chạy, cần quyền tạo tài nguyên trong account):

```sh
# 1. Lưu webhook vào SSM (Terraform không bao giờ giữ giá trị này, nên nó không nằm trong state)
aws ssm put-parameter --name /cost-anomaly/slack-webhook --type SecureString \
  --value 'https://hooks.slack.com/services/...'

# 2. Triển khai
cd infra/terraform
terraform init
terraform apply -var 'slack_webhook_parameter_name=/cost-anomaly/slack-webhook'
#   tùy chọn: -var with_cad=true   -var account_label=project-a
#             -var "config_toml=$(cat ../../demo/cost-anomaly.toml)"

# 3. Chạy thử một lần (không cần đợi lịch)
aws lambda invoke --function-name cost-anomaly out.json && cat out.json
```

Biến Terraform:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `slack_webhook_parameter_name` | `""` | Tên SSM SecureString chứa webhook (bắt đầu bằng `/`). Để trống thì không gửi Slack, chỉ ghi log |
| `slack_webhook_kms_key_arn` | `""` | KMS key tự quản lý của parameter (thêm `kms:Decrypt`). Để trống nếu dùng `alias/aws/ssm` |
| `with_cad` | `false` | Đối chiếu AWS CAD (thêm `ce:GetAnomalies`) |
| `config_toml` | `""` | Nội dung file config TOML, như [File config](#file-config) |
| `account_label` | account ID | Tên hiển thị trong report và Slack |
| `schedule_expression` / `schedule_timezone` | `cron(0 2 * * ? *)` / `UTC` | Lịch chạy |
| `name_prefix` | `cost-anomaly` | Tiền tố tên mọi tài nguyên (function, bucket, role, schedule) |
| `aws_region` | `us-east-1` | Region của Lambda, bucket và lịch (Cost Explorer là global) |
| `report_retention_days` | `90` | Số ngày giữ report trên S3 |
| `log_retention_days` | `30` | Số ngày giữ log (giá trị CloudWatch hỗ trợ) |

Output: `function_name`, `state_bucket`, `log_group_name`, `schedule_name`. Nếu đổi `name_prefix`, dùng `terraform output -raw function_name` khi gọi `aws lambda invoke`.

Kết quả mỗi lần chạy: report ở `s3://<bucket>/reports/<ngày>/` và tin nhắn Slack nếu có sự cố mới/xấu đi. Bản tóm tắt nằm trong CloudWatch Logs. Khi gửi Slack thất bại, lần chạy báo lỗi trên CloudWatch và state không bị ghi, nên hôm sau cảnh báo sẽ được gửi lại.

Chi phí ước tính mỗi tháng: khoảng 30–60 request Cost Explorer (≈ $0.30–0.60; thêm khoảng 30 request nếu bật `with_cad` và AWS có tính phí API này). Lambda, Scheduler, S3 và SSM standard parameter nằm trong free tier hoặc chỉ vài cent.

Kiểm tra cấu hình mà không cần credential (mock provider, chỉ plan):

```sh
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform test
```

## Cách phát hiện

Với `--end-date` = T (mặc định là hôm nay):

- Tool lấy dữ liệu các ngày `[T−90, T)`.
- Đánh giá `--eval-days` ngày đã chốt (mặc định 7, từ T−9 đến T−3).
- Đánh giá thêm 2 ngày gần nhất (T−2, T−1) với nhãn **tạm tính** (`provisional=true`): Cost Explorer chưa chốt số liệu nên con số có thể còn thay đổi, nhưng chạy hằng ngày sẽ thấy chi phí của hôm qua. Dùng `--no-provisional` để bỏ qua hai ngày này như trước.

Mỗi ngày được so với 30 ngày ngay trước nó:

```text
median = trung vị chi phí 30 ngày baseline (ngày không có chi phí tính là $0)
MAD    = trung vị |chi phí − median|
σ̂      = max(1.4826 × MAD, 1% × median, $0.01)
z      = (cost − median) / σ̂

SPIKE        ⇔ baseline có ≥ min_history ngày có chi phí, z > k và cost − median ≥ min_delta
NEW_SERVICE  ⇔ baseline có < min_history ngày có chi phí và cost ≥ new_threshold
DROP         ⇔ đủ lịch sử, median ≥ drop_min_median ($10), cost ≤ drop_ratio (10%) × median và z < −k
```

**DROP** báo khi service đang ổn định bỗng gần như không phát sinh chi phí: backup ngừng, pipeline chết, workload production sập. Cả AWS Cost Anomaly Detection lẫn bản trước của tool đều không báo chiều giảm. Điều kiện được xét trên chi phí thực trả và phải khớp với usage, nên việc mua Savings Plans/RI (chi phí giảm một phần) không bị báo nhầm. Tắt bằng `--no-drop`.

**Tác động tháng** (`month_impact`) = `delta × số ngày từ ngày đó tới hết tháng`, tính cả hai đầu. Con số này trả lời câu hỏi "nếu mức này tiếp diễn thì tháng này tốn thêm bao nhiêu"; với DROP thì âm.

Median và MAD ít bị ảnh hưởng bởi các đỉnh cũ: một ngày tăng vọt trong quá khứ không kéo ngưỡng lên. Ngưỡng `min_delta` loại các biến động có z cao nhưng số tiền nhỏ.

### Savings Plans, RI và nhãn `driver`

Dữ liệu gồm cả usage được Savings Plans/RI che (`SavingsPlanCoveredUsage`, `DiscountedUsage`). Nếu bỏ phần này, khi cam kết hết hạn hoặc coverage thay đổi, usage "xuất hiện" và tool báo spike giả. Mỗi service/ngày có hai số đo, lấy trong cùng một request (không tốn thêm tiền):

- **usage** (`UnblendedCost`): với phần Savings Plans che là giá on-demand tương đương; với phần RI che là $0 (phí RI nằm ở dòng RIFee, không thuộc service).
- **amortized** (`NetAmortizedCost`): chi phí thực trả sau Savings Plans/RI.

Tool chấm cả hai số đo. Một ngày được tính là "có chi phí" nếu một trong hai số đo > 0, nên service chạy hoàn toàn bằng RI không bị coi là service mới. Nếu usage bất thường thì báo theo usage (`metric=usage`). Nếu usage bình thường nhưng chi phí thực trả tăng đột biến thì báo theo amortized (`metric=amortized`).

Nhãn `driver`:

- `usage`: hai số đo cùng tăng, và mức tăng chi phí thực trả nằm trong ±25% mức tăng usage. Nghĩa là dùng nhiều hơn.
- `rate`: các trường hợp còn lại, ví dụ Savings Plans hết hạn (usage phẳng, chi phí thực trả tăng) hoặc RI hết hạn (usage từ $0 lên giá on-demand). Nên xem lại cam kết, không phải workload.

Giới hạn đã biết: nếu usage tăng nhưng phần tăng được Savings Plans còn dư che, chi phí thực trả tăng ít hơn usage nên ngày đó vẫn bị gắn `rate`. Phí cam kết không dùng hết (recurring fee) không được theo dõi.

Lưu ý: một service mới bị gắn NEW_SERVICE **mỗi ngày** cho tới khi baseline của nó có đủ `min_history` ngày có chi phí. Service phát sinh thưa, ví dụ job chạy mỗi tuần một lần, cũng rơi vào trường hợp này. Report có ghi chú riêng cho trường hợp đó.

### Các cột trong CSV

| Cột | Ý nghĩa |
|---|---|
| `date` | Ngày được đánh giá (UTC) |
| `service` | Tên service theo Cost Explorer |
| `kind` | `SPIKE`, `NEW_SERVICE` hoặc `DROP` |
| `cost` | Chi phí trong ngày (USD), theo số đo ở cột `metric` |
| `baseline_median` | Median 30 ngày trước, tức mức "bình thường" |
| `mad` | Median Absolute Deviation của 30 ngày đó |
| `robust_z` | Số lần độ dao động thông thường mà chi phí vượt median; để trống với `NEW_SERVICE` |
| `delta` | `cost − baseline_median`, số USD vượt mức bình thường |
| `metric` | `usage` hoặc `amortized`: số liệu ở các cột trên lấy từ số đo nào |
| `driver` | `usage` (dùng nhiều hơn) hoặc `rate` (do giá/coverage Savings Plans, RI) |
| `provisional` | `true` nếu ngày đó chưa được Cost Explorer chốt số liệu (tạm tính) |
| `month_impact` | `delta × số ngày còn lại trong tháng`: chi phí thêm nếu tiếp diễn |
| `known` | `true` nếu service nằm trong `known` của file config |
| `cad_match` | `true`/`false` khi chạy với `--with-cad` (AWS CAD có/không có anomaly cùng service và ngày); để trống nếu không đối chiếu |

Các dòng được sắp theo ngày mới nhất trước, trong cùng ngày thì `delta` lớn trước.

## Bảo mật

Role có thể có quyền rộng, nhưng tool chỉ dùng đúng phần cần thiết:

- Khi gọi `sts:AssumeRole`, tool gửi kèm một **session policy** chỉ cho phép `ce:GetCostAndUsage` (thêm `ce:GetAnomalies` khi có `--with-cad`). Quyền thực tế là phần giao giữa quyền của role và session policy. Vì vậy credential tạm chỉ đọc được Cost Explorer, kể cả khi bị lộ.
- Trong code, mỗi client có một allowlist API: client STS chỉ gọi được `AssumeRole`, client Cost Explorer chỉ gọi được `GetCostAndUsage` (và `GetAnomalies` khi có `--with-cad`). Session policy và allowlist được tạo từ cùng một danh sách nên không thể lệch nhau.
- Khi chạy trên Lambda, tool không gọi AssumeRole nên không có session policy. Giới hạn quyền nằm ở inline policy của execution role (chỉ đúng các API và ARN ở bảng trên), cộng allowlist trong code: S3 chỉ `GetObject`/`PutObject`, SSM chỉ `GetParameter`, Cost Explorer như CLI.
- Mỗi lần chạy thường tốn 1–2 request Cost Explorer ($0.01/request). `--max-pages` chặn trường hợp phân trang bất thường.

CSV và report chứa dữ liệu chi phí thật của account. Chỉ chia sẻ cho người có quyền xem chi phí, và không commit lên repo. `.gitignore` đã loại `*.csv`, `*_report.html`, `*_report.md` và `*_report.pdf`.

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

Cần mã nguồn (repo). Demo chạy CLI thật trên AWS giả lập: file config tạm, MFA giả, STS và Cost Explorer được stub bằng `botocore.stub.Stubber`. Dữ liệu là số liệu tổng hợp có cài sẵn các kịch bản: EC2 tăng đột biến, NAT/data transfer tăng 2 ngày, Bedrock mới xuất hiện, Lambda tăng nhỏ bị lọc, Savings Plans của Fargate hết hạn, RI của ElastiCache hết hạn, CloudWatch tăng vọt hôm qua (tạm tính), RDS tăng $7 (chỉ bị báo nhờ ngưỡng riêng trong `demo/cost-anomaly.toml`), AWS Backup ngừng chạy (DROP), Bedrock được đánh dấu `known`. Lần chạy thứ hai dùng `--with-cad` với dữ liệu CAD giả lập (EC2 và ElastiCache trùng với tool, S3 chỉ CAD thấy). Demo chạy hai lần với cùng file state: lần một (hôm qua) ghi nhận sự cố; lần hai (hôm nay, `--alert-dry-run`) chỉ đưa sự cố mới vào tin nhắn Slack. Demo không gọi AWS và không tốn phí.

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
terraform -chdir=infra/terraform init -backend=false && terraform -chdir=infra/terraform test   # test Terraform (mock, không cần credential)
uv build                                   # tạo dist/*.whl và dist/*.tar.gz để phát hành
```

Test không gọi AWS hay Slack thật (`urllib.request.urlopen` được thay bằng stub, biến `COST_ANOMALY_SLACK_WEBHOOK` bị xóa trong mọi test). Chúng dùng credential giả, file config tạm, và response giả lập bằng `botocore.stub.Stubber` cùng các fixture JSON.

Luồng xử lý chính:

- CLI (`cli.main`): `auth` (AssumeRole + session policy) → `pipeline.run`: `guard` (allowlist API) → `fetch` (phân trang) → `transform` (ma trận service × ngày cho từng metric) → `detect` → `cad` (nếu `--with-cad`) → `report` (CSV) → `analysis` → `html_report` / `md_report` → `alerting` (`state` gộp sự cố, `alert` gửi Slack).
- Lambda (`lambda_handler.handler`): config từ `COST_ANOMALY_CONFIG` → webhook từ SSM → state từ S3 → `pipeline.run` (dùng credential của execution role) → CSV/report lên S3 → `alerting`.
- Hạ tầng: `infra/terraform/` (test trong `infra/terraform/tests/`). Spec từng tính năng nằm trong `specs/`.
