# -*- coding: utf-8 -*-
"""
Dashboard de Financiamiento de Facturas - Integrado con estructura de tasas, análisis por riesgo, y haircut según producto.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from io import BytesIO
import os

st.set_page_config(layout="wide")
st.title("Dashboard de Financiamiento de Facturas")

# === RUTAS POR DEFECTO ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FACTURAS = os.path.join(BASE_DIR, "data", "facturas_ejemplo.xlsx")
DEFAULT_TASAS = os.path.join(BASE_DIR, "data", "estructura_tasas.xlsx")

# === SIDEBAR ===
with st.sidebar:
    st.header("Carga de datos")
    archivo = st.file_uploader("Archivo Excel de facturas", type=["xlsx"], key="facturas")
    archivo_tasas = st.file_uploader("Estructura de tasas", type=["xlsx"], key="tasas")

# Usar archivos por defecto si no se suben
if not archivo and os.path.exists(DEFAULT_FACTURAS):
    with open(DEFAULT_FACTURAS, "rb") as f:
        archivo = BytesIO(f.read())
        archivo.name = "facturas_ejemplo.xlsx"

if not archivo_tasas and os.path.exists(DEFAULT_TASAS):
    with open(DEFAULT_TASAS, "rb") as f:
        archivo_tasas = BytesIO(f.read())
        archivo_tasas.name = "estructura_tasas.xlsx"

# === MAIN ===
if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"Fecha Emisión": "Fecha_Emision"})
    df["Fecha_Emision"] = pd.to_datetime(df["Fecha_Emision"], dayfirst=True, errors='coerce')
    df["Fecha_Vencimiento"] = pd.to_datetime(df["Fecha_Vencimiento"], dayfirst=True, errors='coerce')

    # Calcular haircut según tipo de producto
    haircut_dict = {
        "Fruta": 0.15,
        "Vino": 0.20,
        "Otros": 0.30
    }
    df["Haircut"] = df["Producto"].map(haircut_dict).fillna(0.25)
    df["Monto con Haircut"] = df["Valor Factura (USD)"] * (1 - df["Haircut"])

    # === FILTROS ===
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        exportador = st.selectbox("Exportador", ["Todos"] + sorted(df["Exportador"].dropna().unique().tolist()))
    with col_f2:
        importador = st.selectbox("Importador", ["Todos"] + sorted(df["Importador"].dropna().unique().tolist()))
    with col_f3:
        estado = st.selectbox("Estado", ["Todos"] + sorted(df["Estado"].dropna().unique().tolist()))
    with col_f4:
        fecha_referencia = st.date_input("Fecha base", value=datetime.today())

    df["Dias_al_Vencimiento"] = (df["Fecha_Vencimiento"] - pd.to_datetime(fecha_referencia)).dt.days
    df = df[df["Dias_al_Vencimiento"] >= 0]  # Excluir facturas vencidas

    def nivel_dra(score):
        if pd.isna(score): return "Desconocido"
        elif score >= 9: return "Muy Bajo"
        elif score >= 7: return "Bajo"
        elif score >= 5: return "Medio"
        elif score >= 3: return "Alto"
        else: return "Muy Alto"

    df["Riesgo"] = df["Score Riesgo"].apply(nivel_dra)

    if archivo_tasas:
        tasas_df = pd.read_excel(archivo_tasas)
        tasas_df = tasas_df.set_index("Riesgo")

        def buscar_tasa(riesgo, dias):
            if pd.isna(riesgo) or riesgo not in tasas_df.index: return None
            for plazo in [30, 60, 90, 120, 150]:
                if dias <= plazo:
                    return tasas_df.loc[riesgo, f"{plazo} dias"]
            return tasas_df.loc[riesgo, "150 dias"]

        df["Tasa Aplicada"] = df.apply(lambda row: buscar_tasa(row["Riesgo"], row["Dias_al_Vencimiento"]), axis=1)
        df["Tasa Aplicada"] = df["Tasa Aplicada"] / 100

    df_filtrado = df.copy()
    if exportador != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Exportador"] == exportador]
    if importador != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Importador"] == importador]
    if estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Estado"] == estado]

    total_monto = df_filtrado["Valor Factura (USD)"].sum()
    facturas_financiables = df_filtrado[df_filtrado["Estado"] != "No Financiable"]["Valor Factura (USD)"].sum()
    total_financiado = df_filtrado["Monto Financiado (USD)"].sum()
    tasa_promedio = df_filtrado["Tasa Aplicada"].mean() if "Tasa Aplicada" in df_filtrado.columns else None
    haircut_promedio = df_filtrado["Haircut"].mean()
    porcentaje_financiado = total_financiado / facturas_financiables if facturas_financiables > 0 else 0
    duracion_promedio = df_filtrado["Dias_al_Vencimiento"].mean()
    porcentaje_pagadas = df_filtrado[df_filtrado["Pagado"] == "Sí"]["Valor Factura (USD)"].sum() / total_monto if total_monto > 0 else 0
    porcentaje_atrasadas = 1 - porcentaje_pagadas

    plazo_max = df_filtrado["Dias_al_Vencimiento"].max()
    plazo_min = df_filtrado["Dias_al_Vencimiento"].min()
    tasa_max = df_filtrado["Tasa Aplicada"].max()
    tasa_min = df_filtrado["Tasa Aplicada"].min()
    haircut_max = df_filtrado["Haircut"].max()

    col_a, col_b, col_c, col_d, col_e = st.columns(5)
    col_a.metric("Monto total de facturas", f"${total_monto:,.0f}")
    col_b.metric("Facturas Financiables", f"${facturas_financiables:,.0f}")
    col_c.metric("Financiamiento solicitado", f"${total_financiado:,.0f}")
    col_d.metric("Tasa de Interés Promedio", f"{tasa_promedio:.2%}" if tasa_promedio else "N/A")
    col_e.metric("% Haircut Promedio", f"{haircut_promedio:.2%}")

    col_f, col_g, col_h, col_i, col_j = st.columns(5)
    col_f.metric("% de Facturas Financiadas", f"{porcentaje_financiado:.2%}")
    col_g.metric("Duración Promedio (días)", f"{duracion_promedio:.0f}")
    top_exportadores = df_filtrado.groupby("Exportador")["Valor Factura (USD)"].sum().sort_values(ascending=False).head(5)
    col_h.metric("Concentración Top 5 Exportadores", f"{top_exportadores.sum() / total_monto:.2%}" if not top_exportadores.empty else "N/A")
    col_i.metric("% de Facturas Pagadas al Día", f"{porcentaje_pagadas:.2%}")
    col_j.metric("% de Facturas con Retraso", f"{porcentaje_atrasadas:.2%}")

    col_k, col_l, col_m, col_n, col_o = st.columns(5)
    col_k.metric("Plazo Máximo (días)", f"{plazo_max:.0f}")
    col_l.metric("Plazo Mínimo (días)", f"{plazo_min:.0f}")
    col_m.metric("Tasa Máxima Aplicada", f"{tasa_max:.2%}" if tasa_max else "N/A")
    col_n.metric("Tasa Mínima Aplicada", f"{tasa_min:.2%}" if tasa_min else "N/A")
    col_o.metric("% Haircut Máximo", f"{haircut_max:.2%}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Distribución por estado")
        fig_estado = px.pie(df_filtrado, names="Estado", values="Valor Factura (USD)")
        st.plotly_chart(fig_estado, use_container_width=True)

    with col2:
        if archivo_tasas:
            st.subheader("Estructura de tasas por riesgo y plazo")
            tasas_long = tasas_df.reset_index().melt(id_vars="Riesgo", var_name="Plazo", value_name="Tasa")
            tasas_long["Plazo"] = tasas_long["Plazo"].str.extract(r'(\d+)').astype(int)
            tasas_long["Tasa"] = tasas_long["Tasa"] / 100
            fig_tasas = px.line(tasas_long, x="Plazo", y="Tasa", color="Riesgo", markers=True)
            st.plotly_chart(fig_tasas, use_container_width=True)

    col3, col4, col5 = st.columns(3)
    with col3:
        st.subheader("Distribución por Nivel de Riesgo")
        riesgo_group = df_filtrado.groupby("Riesgo")["Valor Factura (USD)"].sum().reset_index()
        fig_riesgo = px.bar(riesgo_group, x="Riesgo", y="Valor Factura (USD)", color="Riesgo")
        st.plotly_chart(fig_riesgo, use_container_width=True)

    with col4:
        st.subheader("% de Facturas Pagadas al Día")
        total_pagadas = df_filtrado[df_filtrado["Pagado"] == "Sí"]["Valor Factura (USD)"].sum()
        total_otras = df_filtrado["Valor Factura (USD)"].sum() - total_pagadas
        fig_pagadas = px.pie(names=["Pagadas al día", "Atrasadas"], values=[total_pagadas, total_otras])
        st.plotly_chart(fig_pagadas, use_container_width=True)

    with col5:
        st.subheader("Flujo de Vencimientos")
        vencimientos = df_filtrado.dropna(subset=["Fecha_Vencimiento"])
        vencimientos_group = vencimientos.groupby(vencimientos["Fecha_Vencimiento"].dt.to_period("M")).agg({"Valor Factura (USD)": "sum"}).reset_index()
        vencimientos_group["Fecha_Vencimiento"] = vencimientos_group["Fecha_Vencimiento"].dt.to_timestamp()
        fig_vencimientos = px.bar(vencimientos_group, x="Fecha_Vencimiento", y="Valor Factura (USD)")
        st.plotly_chart(fig_vencimientos, use_container_width=True)

    st.subheader("Detalle de facturas")
    st.dataframe(df_filtrado, use_container_width=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_filtrado.to_excel(writer, index=False)
    output.seek(0)

    st.download_button(
        label="Descargar Excel filtrado",
        data=output,
        file_name="facturas_filtradas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Por favor, sube el archivo Excel para comenzar o asegúrate que estén los archivos por defecto en la carpeta 'data/'.")
