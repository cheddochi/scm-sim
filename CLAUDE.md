# CLAUDE.md - 배터리 공급망 시뮬레이터

- 설계 문서: 디자인.md, 대화요약.md (프로젝트 루트). 구현 전에 먼저 읽는다.
- 환경: ~/venv-scm (Python, gurobipy, highspy, streamlit, plotly). Gurobi 실패 시 HiGHS로 자동 전환.
- 연도별 LP는 연도별로 분리해서 푼다(변수 수를 줄이기 위해).
- 작업 규칙: 의미 있는 단위로 작업을 끝낼 때마다
  1. `./py -m pytest tests/test_benchmarks.py -q`로 벤치마크를 돌리고 (venv가 x86_64라 `./py`가 Rosetta로 실행)
  2. PROGRESS.md의 벤치마크 표와 '다음 작업'을 갱신하고
  3. `git add -A && git commit -m "<요약>" && git push`
  사용자는 출근 중 휴대폰 Claude 앱에서 이 저장소로 현황을 확인한다.
- 사용자 선호: 결론 30자 내외 두괄식, 시사점 함께 제시, 수학은 사설 없이 계산·검증 결과를 바로 제시.
