"""一键部署到腾讯云轻量服务器（Ubuntu）。

用法（密码不落盘，仅命令行传入）:
    python scripts/deploy_tencent.py --host 139.155.157.248 --password <密码> [--skip-upload]

站点免费模式（访客免配置直接提问）需额外传入站点共享 Key，并可选调额度：
    python scripts/deploy_tencent.py --host <ip> --password <pw> \\
        --llm-api-key <站点共享 Key> \\
        --llm-base-url https://open.bigmodel.cn/api/paas/v4 \\
        --llm-model glm-4.7-flash \\
        --free-per-hour 10 --free-per-day 30 --free-global-per-day 500

Key 只经命令行传入并写入服务器上的 systemd 单元（600 权限），不进仓库。

流程: 连通测试 → 上传代码包(git archive) → 服务器初始化(swap/venv/依赖)
      → systemd 服务 → 健康检查。
"""
from __future__ import annotations

import argparse
import subprocess
import sys

import paramiko

APP_DIR = "/opt/poke-rag"
UNIT_TMPL = """[Unit]
Description=Poke-RAG Streamlit app
After=network.target

[Service]
WorkingDirectory=/opt/poke-rag
Environment=EMBED_DISABLED=1
Environment=LLM_BASE_URL={base_url}
Environment=LLM_MODEL={model}
{extra}ExecStart=/opt/poke-rag/.venv/bin/streamlit run app_render.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def build_unit(base_url: str, model: str, api_key: str | None,
               free: dict | None = None) -> str:
    """生成 systemd 单元。站点共享 Key 与限流额度作为 Environment 注入。"""
    lines = []
    if api_key:
        lines.append(f"Environment=LLM_API_KEY={api_key}\n")
    if free:
        for k, v in free.items():
            if v is not None:
                lines.append(f"Environment={k}={v}\n")
    return UNIT_TMPL.format(base_url=base_url, model=model, extra="".join(lines))


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 300) -> int:
    print(f"\n$ {cmd}")
    code = -1
    _, out, err = ssh.exec_command(cmd, timeout=timeout)
    text = out.read().decode("utf-8", "replace")
    etext = err.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    tail = text.strip()
    if tail:
        print(tail[-3000:])
    if etext.strip():
        print("[stderr]", etext[-1500:])
    print(f"[exit {code}]")
    return code


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--user", default="ubuntu")
    ap.add_argument("--skip-upload", action="store_true")
    # 站点免费模式（可选）：传了 Key 才有"访客免配置直接用"
    ap.add_argument("--llm-api-key", default=None,
                    help="站点共享 Key（写入服务器 systemd，不进仓库）")
    ap.add_argument("--llm-base-url", default="https://open.bigmodel.cn/api/paas/v4")
    ap.add_argument("--llm-model", default="glm-4.7-flash")
    ap.add_argument("--free-per-hour", type=int, default=None)
    ap.add_argument("--free-per-day", type=int, default=None)
    ap.add_argument("--free-global-per-day", type=int, default=None)
    args = ap.parse_args()

    free_env = {
        "FREE_PER_HOUR": args.free_per_hour,
        "FREE_PER_DAY": args.free_per_day,
        "FREE_GLOBAL_PER_DAY": args.free_global_per_day,
    }
    unit = build_unit(args.llm_base_url, args.llm_model, args.llm_api_key, free_env)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"connect {args.user}@{args.host} ...")
    ssh.connect(args.host, 22, args.user, args.password, timeout=30, banner_timeout=30)
    print("connected.")

    steps = [
        ("system check", "uname -a && cat /etc/os-release | head -2 && free -h | head -2 && df -h / | tail -1"),
        ("swap", (
            "swapon --show=NAME | grep -q '/swapfile' || { sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile "
            "&& sudo mkswap /swapfile && sudo swapon /swapfile; }; "
            "grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null; free -h | head -2"
        )),
        ("apt base", "sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv python3-pip unzip > /dev/null && python3 -V"),
    ]
    for name, cmd in steps:
        print(f"\n=== {name} ===")
        if run(ssh, cmd, timeout=600) != 0:
            sys.exit(f"step failed: {name}")

    if not args.skip_upload:
        subprocess.run(
            ["git", "archive", "--format=zip", "--output=_deploy.zip", "HEAD"],
            check=True,
        )
        print("\n=== upload _deploy.zip (SFTP) ===")
        sftp = ssh.open_sftp()
        sftp.put("_deploy.zip", "/home/ubuntu/poke-rag-deploy.zip")
        sftp.close()
        print("uploaded.")

    deploy_steps = [
        ("unpack", f"sudo mkdir -p {APP_DIR} && sudo chown ubuntu:ubuntu {APP_DIR} && cd {APP_DIR} && unzip -o -q /home/ubuntu/poke-rag-deploy.zip && ls | head"),
        ("venv", (
            f"cd {APP_DIR} && python3 -m venv .venv && "
            ".venv/bin/pip install -q -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple && "
            ".venv/bin/pip install -q -r requirements-render.txt "
            "-i https://pypi.tuna.tsinghua.edu.cn/simple && .venv/bin/python -V"
        )),
        ("unit file", f"sudo tee /etc/systemd/system/poke-rag.service > /dev/null << 'EOF'\n{unit}\nEOF\nsudo chmod 600 /etc/systemd/system/poke-rag.service\nsudo systemctl daemon-reload"),
        ("start", "sudo systemctl enable poke-rag && sudo systemctl restart poke-rag && sleep 8 && systemctl is-active poke-rag"),
        ("health", "sleep 3; curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8501"),
    ]
    for name, cmd in deploy_steps:
        print(f"\n=== {name} ===")
        if run(ssh, cmd, timeout=1200) != 0:
            sys.exit(f"step failed: {name}")

    print("\n=== service log tail ===")
    run(ssh, "journalctl -u poke-rag -n 15 --no-pager")
    run(ssh, "sudo rm -f /root/poke-rag-deploy.zip /home/ubuntu/poke-rag-deploy.zip")
    ssh.close()
    print(f"\nDONE. App: http://{args.host}:8501")


if __name__ == "__main__":
    main()
