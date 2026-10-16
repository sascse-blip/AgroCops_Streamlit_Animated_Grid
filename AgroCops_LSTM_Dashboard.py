import random
import time
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import plotly.graph_objects as go

try:
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    tf = None
    TENSORFLOW_AVAILABLE = False
import streamlit as st
import streamlit.components.v1 as components


SEQUENCE_LENGTH = 12

@st.cache_resource
def train_lstm_model():
    """Train a demonstration LSTM on synthetic time-series data.

    This is a proof-of-concept model only. It must be retrained on real,
    labelled storage-sensor data before being used for operational decisions.
    """
    if not TENSORFLOW_AVAILABLE:
        return None

    # Fixed seeds make the demo model reproducible.
    np.random.seed(42)
    tf.random.set_seed(42)
    rng = np.random.default_rng(42)

    sample_count = 700
    X = np.zeros((sample_count, SEQUENCE_LENGTH, 3), dtype=np.float32)
    y = np.zeros((sample_count, 1), dtype=np.float32)

    for i in range(sample_count):
        baseline_gas = rng.uniform(220, 1100)
        trend = rng.uniform(-8, 14)
        baseline_temp = rng.uniform(24, 34)
        baseline_humidity = rng.uniform(45, 82)
        gas_series = []
        for t in range(SEQUENCE_LENGTH + 1):
            gas_value = np.clip(
                baseline_gas + trend * t + 22 * np.sin(t / 2.0) + rng.normal(0, 12),
                150, 1400
            )
            temp_value = np.clip(
                baseline_temp + 0.25 * np.sin(t / 3.0) + rng.normal(0, 0.15),
                18, 45
            )
            humidity_value = np.clip(
                baseline_humidity + 2.0 * np.cos(t / 4.0) + rng.normal(0, 1.0),
                25, 95
            )
            gas_series.append([gas_value / 1500.0, temp_value / 50.0, humidity_value / 100.0])

        X[i] = np.asarray(gas_series[:SEQUENCE_LENGTH], dtype=np.float32)
        y[i, 0] = gas_series[SEQUENCE_LENGTH][0]

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(SEQUENCE_LENGTH, 3)),
        tf.keras.layers.LSTM(16),
        tf.keras.layers.Dense(8, activation="relu"),
        tf.keras.layers.Dense(1, activation="sigmoid")
    ])
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    model.fit(X, y, epochs=5, batch_size=32, validation_split=0.1, verbose=0)
    return model


def classify_gas_level(gas_value):
    if gas_value >= 1000:
        return "CRITICAL"
    if gas_value >= 400:
        return "WARNING"
    return "NOMINAL"


def predict_next_gas(model, current_gas, temperature, humidity, seed_value):
    """Build a demo sequence and predict the next gas/VOC-like reading."""
    rng = np.random.default_rng(seed_value)
    recent_gas = np.linspace(max(150, current_gas - 25), current_gas, SEQUENCE_LENGTH)
    recent_gas += rng.normal(0, 8, SEQUENCE_LENGTH)
    recent_temp = temperature + rng.normal(0, 0.15, SEQUENCE_LENGTH)
    recent_humidity = humidity + rng.normal(0, 1.0, SEQUENCE_LENGTH)

    sequence = np.column_stack([
        np.clip(recent_gas, 150, 1400) / 1500.0,
        np.clip(recent_temp, 18, 45) / 50.0,
        np.clip(recent_humidity, 25, 95) / 100.0
    ]).astype(np.float32)

    prediction = float(model.predict(sequence[np.newaxis, :, :], verbose=0)[0][0])
    return int(np.clip(prediction * 1500.0, 0, 1500))


st.set_page_config(page_title="AgroCops Central Command", page_icon="🌱", layout="wide")

st.markdown("""
<style>
.stApp { background:#0b0f12; color:#f3f6f8; }
.block-container { max-width: 1800px; padding-top:1rem; padding-bottom:2rem; }
h1,h2,h3 { color:#f3f6f8; }
[data-testid="stMetric"] { background:#151c21; border:1px solid #2b3941; padding:12px; border-radius:10px; }
.small-note {color:#9eabb4;font-size:.9rem}
.status-pill {display:inline-block;padding:5px 10px;border-radius:999px;font-weight:700;font-size:.8rem}
@keyframes pulse { 0%,100% { box-shadow:0 0 0 0 rgba(0,255,110,.18); } 50% { box-shadow:0 0 0 4px rgba(0,255,110,.03), 0 0 14px rgba(0,255,110,.25); } }
@keyframes warningPulse { 0%,100% { filter:brightness(1); } 50% { filter:brightness(1.45); } }
@keyframes scan { 0% { transform:translateX(-110%); } 100% { transform:translateX(110%); } }
</style>
""", unsafe_allow_html=True)

st.title("🌱 AGROCOPS CENTRAL COMMAND")
st.caption("Smart Harvest Security System · Simulated demo mode · No physical sensors required")

with st.sidebar:
    st.header("Demo Controls")
    auto_refresh = st.toggle("Animate live readings", value=True)
    refresh_seconds = st.slider("Refresh interval (seconds)", 2, 10, 3)
    seed = st.number_input("Dataset seed", min_value=1, max_value=99999, value=42)
    st.markdown("**Grid legend**")
    st.markdown("🟩 Nominal · 🟧 Warning · 🟥 Critical")
    st.info("All values are simulated and are not actual sensor measurements.")

random.seed(int(seed))
now = datetime.now()
if "sample_tick" not in st.session_state:
    st.session_state.sample_tick = 0
tick = st.session_state.sample_tick

sensors = []
for r in range(10):
    for c in range(10):
        sensor_id = f"S-{r}-{c}"
        rng = random.Random(int(seed) * 1000 + r * 10 + c)
        gas = max(180, int(rng.gauss(300, 35)))
        temp = round(rng.gauss(28.3, 0.7), 1)
        humidity = max(35, min(90, int(rng.gauss(65, 4))))
        # Fixed example anomalies so warning/critical states are visible in every demo.
        if (r, c) in [(1, 7), (4, 2), (7, 8)]:
            gas = 450 + ((tick * 13 + r * 9 + c) % 250)
        if (r, c) in [(3, 4), (8, 1)]:
            gas = 1050 + ((tick * 17 + r * 5 + c) % 250)
        # Small movement in the simulated readings while refreshing.
        gas = max(0, gas + random.randint(-10, 10) if tick else gas)
        temp = round(temp + (random.uniform(-0.3, 0.3) if tick else 0), 1)
        humidity = max(20, min(95, humidity + (random.randint(-1, 1) if tick else 0)))
        if gas >= 1000:
            status, color, css_class = "CRITICAL", "#e32636", "critical"
        elif gas >= 400:
            status, color, css_class = "WARNING", "#ff8500", "warning"
        else:
            status, color, css_class = "NOMINAL", "#087d20", "nominal"
        sensors.append({"id":sensor_id,"row":r,"col":c,"gas":gas,"temperature":temp,
                        "humidity":humidity,"status":status,"color":color,"css_class":css_class})
df = pd.DataFrame(sensors)
counts = df.status.value_counts()
nominal_count = int(counts.get("NOMINAL", 0))
warning_count = int(counts.get("WARNING", 0))
critical_count = int(counts.get("CRITICAL", 0))

m1,m2,m3,m4 = st.columns(4)
m1.metric("Total Modules", len(df))
m2.metric("Nominal", nominal_count)
m3.metric("Warnings", warning_count)
m4.metric("Critical", critical_count)

st.subheader("Sensor Grid · 10 × 10")
st.markdown('<div class="small-note">Green = nominal · Orange = warning · Red = critical. Animated glow indicates the dashboard is refreshing simulated readings.</div>', unsafe_allow_html=True)

# Browser-rendered color tiles with animated working indicators.
tiles = []
for item in df.to_dict("records"):
    animation = "pulse 1.8s infinite" if item["status"] == "NOMINAL" else "warningPulse 1.2s infinite"
    icon = "●" if item["status"] == "NOMINAL" else ("▲" if item["status"] == "WARNING" else "✖")
    tiles.append(
        f"""<div class="tile {item['css_class']}" title="{item['id']} · {item['status']} · value {item['gas']}"
        style="background:{item['color']};animation:{animation};">
        <span class="sensor-name">{item['id']}</span><span class="sensor-state">{icon}</span>
        </div>"""
    )
grid_html = """
<style>
*{box-sizing:border-box}
.sensor-grid{display:grid;grid-template-columns:repeat(10,minmax(0,1fr));gap:6px;width:100%;font-family:Arial,sans-serif}
.tile{height:54px;border-radius:5px;border:1px solid rgba(255,255,255,.16);display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;position:relative;overflow:hidden}
.tile:after{content:"";position:absolute;top:0;bottom:0;width:30%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.18),transparent);animation:scan 3.5s linear infinite}
.sensor-name{font-size:12px;font-weight:700;z-index:1}
.sensor-state{font-size:10px;opacity:.85;z-index:1;margin-top:2px}
.nominal{border-color:#18d34b}
.warning{border-color:#ffbd66}
.critical{border-color:#ff7880}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(0,255,110,.08);filter:brightness(.94)}50%{box-shadow:0 0 10px rgba(0,255,110,.28);filter:brightness(1.15)}}
@keyframes warningPulse{0%,100%{filter:brightness(.95)}50%{filter:brightness(1.35)}}
@keyframes scan{0%{left:-35%}100%{left:110%}}
@media(max-width:900px){.sensor-grid{gap:3px}.tile{height:42px}.sensor-name{font-size:9px}.sensor-state{font-size:8px}}
</style>
<div class="sensor-grid">""" + "".join(tiles) + "</div>"
components.html(grid_html, height=610, scrolling=False)

st.divider()
st.subheader("Sensor Details")
sensor_ids = df["id"].tolist()
default_id = "S-3-4"
selected_id = st.selectbox("Choose a sensor to inspect", sensor_ids,
                           index=sensor_ids.index(st.session_state.get("selected_sensor", default_id)))
st.session_state.selected_sensor = selected_id
selected = df[df.id == selected_id].iloc[0]
st.markdown(f"**{selected['id']}** &nbsp; <span class='status-pill' style='background:{selected['color']};color:white'>{selected['status']}</span>", unsafe_allow_html=True)

g1,g2,g3 = st.columns(3)
g1.metric("Temperature", f"{selected['temperature']:.1f} °C")
g2.metric("Humidity", f"{selected['humidity']} %")
g3.metric("Gas / VOC-like level", f"{selected['gas']}")

st.divider()
st.subheader("LSTM-Based Next-Reading Prediction")
st.caption(
    "Proof-of-concept prediction using a model trained on synthetic time-series data. "
    "It is not a validated spoilage detector."
)

if TENSORFLOW_AVAILABLE:
    with st.spinner("Preparing the demonstration LSTM model (first run only)..."):
        lstm_model = train_lstm_model()

    predicted_gas = predict_next_gas(
        lstm_model,
        float(selected["gas"]),
        float(selected["temperature"]),
        float(selected["humidity"]),
        int(seed) + int(selected["row"]) * 10 + int(selected["col"]) + tick
    )
    predicted_status = classify_gas_level(predicted_gas)

    p1, p2, p3 = st.columns(3)
    p1.metric("Predicted next gas/VOC-like level", predicted_gas,
              delta=f"{predicted_gas - int(selected['gas']):+d} vs current")
    p2.metric("Predicted risk category", predicted_status)
    p3.metric("Model", "LSTM · 12 time steps")

    if predicted_status == "CRITICAL":
        st.error("LSTM demo prediction: the next reading may reach the critical threshold.")
    elif predicted_status == "WARNING":
        st.warning("LSTM demo prediction: the next reading may reach the warning threshold.")
    else:
        st.success("LSTM demo prediction: the next reading is below the warning threshold.")

    st.info(
        "Thresholds shown here are illustrative demo thresholds. For real deployment, "
        "train and validate the model using measured storage data and expert-confirmed "
        "spoilage labels."
    )
else:
    st.warning(
        "TensorFlow is not installed, so the LSTM prediction panel is unavailable. "
        "Install the packages listed in requirements.txt and restart the app."
    )


def gauge(title, value, maximum, suffix, bar_color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value, title={"text":title,"font":{"color":"white"}},
        number={"suffix":suffix,"font":{"color":"white"}},
        gauge={"axis":{"range":[0,maximum],"tickcolor":"white"},
               "bar":{"color":bar_color},"bgcolor":"#1c2227","bordercolor":"#39434b",
               "steps":[{"range":[0,maximum*.7],"color":"#263039"},
                        {"range":[maximum*.7,maximum],"color":"#3a2a1e"}]}
    ))
    fig.update_layout(height=240,margin=dict(l=15,r=15,t=45,b=10),paper_bgcolor="#0b0f12",font_color="white")
    return fig

c1,c2=st.columns(2)
with c1:
    st.plotly_chart(gauge("Temperature",float(selected["temperature"]),50," °C","#00d4ff"),use_container_width=True)
with c2:
    st.plotly_chart(gauge("Humidity",float(selected["humidity"]),100," %","#00d4ff"),use_container_width=True)

rng = random.Random(int(seed) + int(selected["row"])*10 + int(selected["col"]) + tick)
times = [now-timedelta(seconds=49-i) for i in range(50)]
values = [max(0,int(selected["gas"]+rng.randint(-25,25))) for _ in range(50)]
line_color = selected["color"]
trend = go.Figure(go.Scatter(x=times,y=values,mode="lines+markers",name="Gas / VOC-like level",
                             line=dict(color=line_color,width=2),marker=dict(size=4)))
trend.update_layout(title="Live Simulated Spoilage-Risk Trend",xaxis_title="Time",yaxis_title="Gas / VOC-like level",
                    paper_bgcolor="#0b0f12",plot_bgcolor="#151c21",font_color="white",height=380,
                    margin=dict(l=20,r=20,t=55,b=25))
trend.update_xaxes(gridcolor="#39434b")
trend.update_yaxes(gridcolor="#39434b",rangemode="tozero")
st.plotly_chart(trend,use_container_width=True)

st.subheader("Dataset Preview")
st.dataframe(df[["id","temperature","humidity","gas","status"]],use_container_width=True,hide_index=True)
st.caption(f"Last refreshed: {now.strftime('%Y-%m-%d %H:%M:%S')} · Synthetic demo data only; not validated for real spoilage detection.")

if auto_refresh:
    time.sleep(refresh_seconds)
    st.session_state.sample_tick += 1
    st.rerun()
