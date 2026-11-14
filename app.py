import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import random

# Configuração da página
st.set_page_config(page_title="NOC - Centro de Controle Operacional", layout="wide", page_icon="📡")

# --- BANCO DE DADOS (SQLite) ---
def init_db():
    conn = sqlite3.connect('noc_sistema_pronto.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS ativos 
                 (id TEXT PRIMARY KEY, nome TEXT, tipo TEXT, ip TEXT, status TEXT, ultima_inspecao TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS ocorrencias 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, ativo_id TEXT, descricao TEXT, 
                  tecnico TEXT, status TEXT, data_abertura TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS checklists 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, tarefa TEXT, status TEXT, responsavel TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS turnos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, operador TEXT, resumo TEXT, melhoria_sugerida TEXT, data TEXT)''')
    
    # Verifica se está vazio (corrigido com)
    c.execute("SELECT COUNT(*) FROM ativos")
    if c.fetchone()[0] == 0:
        ativos_iniciais = [
            ('CAM-01', 'Câmera Portaria Principal', 'Câmera', '192.168.1.101', 'Online', 'Agora'),
            ('CAM-02', 'Câmera Galpão B', 'Câmera', '192.168.1.102', 'Online', 'Agora'),
            ('SEN-01', 'Sensor Temperatura CPD', 'Sensor', '192.168.1.105', 'Online', 'Agora'),
            ('RTR-01', 'Switch Core Redundante', 'Rede', '192.168.1.1', 'Online', 'Agora')
        ]
        c.executemany("INSERT INTO ativos VALUES (?,?,?,?,?,?)", ativos_iniciais)
        
        checklists_iniciais = [
            ('Verificar gravação NVR (últimas 24h)', 'Pendente', 'Operador Turno A'),
            ('Testar redundância de link de internet', 'Concluído', 'Operador Turno A'),
            ('Conferir temperatura dos racks', 'Pendente', 'Operador Turno B')
        ]
        c.executemany("INSERT INTO checklists (tarefa, status, responsavel) VALUES (?,?,?)", checklists_iniciais)
        
    conn.commit()
    return conn

conn = init_db()

# --- INTERFACE VISUAL ---
st.title("📡 Sistema Integrado de Monitoramento e Operações (NOC)")
st.markdown("Painel de controle para inspeção remota, gestão de falhas e passagem de turno.")

menu = st.sidebar.radio("Módulos Operacionais", [
    "1. Monitoramento & Inspeção Remota",
    "2. Ocorrências & Acionamento Técnico",
    "3. Checklists de Manutenção",
    "4. Passagem de Turno & Melhorias"
])

# --- MÓDULO 1: MONITORAMENTO ---
if menu == "1. Monitoramento & Inspeção Remota":
    st.header("Monitoramento em Tempo Real")
    
    df_ativos = pd.read_sql_query("SELECT * FROM ativos", conn)
    
    col1, col2, col3 = st.columns(3)
    total = len(df_ativos)
    online = len(df_ativos[df_ativos['status'] == 'Online'])
    offline = total - online
    
    col1.metric("Total de Ativos", total)
    col2.metric("Sistemas Online", online)
    col3.metric("Falhas Detectadas", offline, delta_color="inverse")
    
    st.divider()
    
    if st.button("🔄 Executar Inspeção Remota Agora (Ping/Stream)"):
        c = conn.cursor()
        agora = datetime.now().strftime("%H:%M:%S")
        for index, row in df_ativos.iterrows():
            novo_status = "Offline" if random.random() < 0.25 else "Online"
            c.execute("UPDATE ativos SET status = ?, ultima_inspecao = ? WHERE id = ?", (novo_status, agora, row['id']))
            
            if novo_status == "Offline" and row['status'] == "Online":
                c.execute("INSERT INTO ocorrencias (ativo_id, descricao, tecnico, status, data_abertura) VALUES (?,?,?,?,?)",
                          (row['id'], f"Falha de comunicação detectada na inspeção remota ({row['ip']})", "Aguardando Acionamento", "Aberto", agora))
        conn.commit()
        st.rerun()

    def colorir_status(val):
        color = '#ff4b4b' if val == 'Offline' else '#09ab3b'
        return f'color: {color}; font-weight: bold'

    st.dataframe(df_ativos.style.map(colorir_status, subset=['status']), width="stretch")

# --- MÓDULO 2: OCORRÊNCIAS ---
elif menu == "2. Ocorrências & Acionamento Técnico":
    st.header("Gestão de Falhas e Apoio ao Campo")
    
    with st.expander("➕ Registrar Nova Ocorrência Manualmente"):
        with st.form("nova_ocorrencia"):
            ativo = st.selectbox("Ativo Afetado", ["CAM-01", "CAM-02", "SEN-01", "RTR-01"])
            desc = st.text_input("Descrição da Falha")
            tecnico = st.selectbox("Acionar Técnico de Campo", ["Carlos Silva (Redes)", "Ana Souza (CFTV)", "Marcos Lima (Elétrica)"])
            if st.form_submit_button("Registrar e Acionar Técnico"):
                c = conn.cursor()
                agora = datetime.now().strftime("%d/%m %H:%M")
                c.execute("INSERT INTO ocorrencias (ativo_id, descricao, tecnico, status, data_abertura) VALUES (?,?,?,?,?)",
                          (ativo, desc, tecnico, "Em Atendimento", agora))
                conn.commit()
                st.success(f"Chamado aberto! Notificação enviada para {tecnico}.")
                st.rerun()

    df_ocorrencias = pd.read_sql_query("SELECT * FROM ocorrencias ORDER BY id DESC", conn)
    st.dataframe(df_ocorrencias, width="stretch")
    
    if not df_ocorrencias.empty:
        st.subheader("Atualizar Status de Ocorrência")
        col1, col2, col3 = st.columns(3)
        id_chamado = col1.number_input("ID do Chamado", min_value=1, step=1)
        novo_tecnico = col2.selectbox("Atribuir/Alterar Técnico", ["Carlos Silva (Redes)", "Ana Souza (CFTV)", "Marcos Lima (Elétrica)"])
        novo_status = col3.selectbox("Novo Status", ["Em Atendimento", "Resolvido"])
        
        if st.button("Salvar Atualização"):
            c = conn.cursor()
            c.execute("UPDATE ocorrencias SET tecnico = ?, status = ? WHERE id = ?", (novo_tecnico, novo_status, id_chamado))
            conn.commit()
            st.success("Ocorrência atualizada!")
            st.rerun()

# --- MÓDULO 3: CHECKLISTS ---
elif menu == "3. Checklists de Manutenção":
    st.header("Acompanhamento de Checklists e Pendências")
    df_check = pd.read_sql_query("SELECT * FROM checklists", conn)
    
    for index, row in df_check.iterrows():
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.write(f"**{row['tarefa']}** (Resp: {row['responsavel']})")
        col2.write(f"Status: `{row['status']}`")
        if row['status'] == 'Pendente':
            if col3.button("Concluir", key=f"chk_{row['id']}"):
                c = conn.cursor()
                c.execute("UPDATE checklists SET status = 'Concluído' WHERE id = ?", (row['id'],))
                conn.commit()
                st.rerun()

# --- MÓDULO 4: PASSAGEM DE TURNO ---
elif menu == "4. Passagem de Turno & Melhorias":
    st.header("Registro de Passagem de Turno e Melhoria Contínua")
    
    with st.form("form_turno"):
        operador = st.text_input("Nome do Operador")
        resumo = st.text_area("Resumo Operacional e Pendências para o Próximo Turno")
        melhoria = st.text_area("Sugestão de Melhoria nos Processos ou Manuais (Opcional)")
        
        if st.form_submit_button("Registrar Passagem de Turno"):
            c = conn.cursor()
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            c.execute("INSERT INTO turnos (operador, resumo, melhoria_sugerida, data) VALUES (?,?,?,?)",
                      (operador, resumo, melhoria, agora))
            conn.commit()
            st.success("Passagem de turno registrada com sucesso!")
            
    st.subheader("Histórico de Turnos")
    df_turnos = pd.read_sql_query("SELECT * FROM turnos ORDER BY id DESC", conn)
    st.dataframe(df_turnos, width="stretch")
