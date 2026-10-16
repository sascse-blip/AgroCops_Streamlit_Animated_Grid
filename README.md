# AgroCops Streamlit Demo

Browser-based, sensor-free AgroCops dashboard. All readings are synthetic.

## Run locally
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy with Streamlit Community Cloud
1. Upload `app.py` and `requirements.txt` to the root of a GitHub repository.
2. Open https://share.streamlit.io/
3. Select the repository, branch `main`, and main file path `app.py`.
4. Click Deploy.

The grid uses green for nominal, orange for warning, red for critical, with animated glow and a scanning highlight. Values are simulated only.
