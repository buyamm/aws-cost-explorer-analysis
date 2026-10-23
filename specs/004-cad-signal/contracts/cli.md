# Contract: --with-cad (004)

| Flag | Effect |
|------|--------|
| `--with-cad` | Session policy and CE allowlist gain `ce:GetAnomalies`; fetch CAD anomalies for the evaluated days |

Session policy with the flag:

```json
{"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["ce:GetAnomalies", "ce:GetCostAndUsage"], "Resource": "*"}]}
```

Without the flag (unchanged): `"Action": "ce:GetCostAndUsage"`.

CSV: `cad_match` appended — `true` | `false` | empty (CAD not requested or unavailable).
