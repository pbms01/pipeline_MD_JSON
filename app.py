"""
app.py - Interface Streamlit para o Pipeline MD/JSON v3.

Esta aplicação fornece uma interface web para:
- Upload de documentos (PDF, DOCX)
- Configuração de opções de processamento
- Visualização de resultados (Markdown, JSON)
- Download dos arquivos gerados
"""
import streamlit as st
from pathlib import Path
import tempfile
import json
import time
from typing import Optional

# Configurar página
st.set_page_config(
    page_title="Pipeline MD/JSON v3",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Imports do projeto
try:
    from converter import convert_document, ConversionConfig
    from converter.detector import detect_document
    CONVERTER_AVAILABLE = True
except ImportError as e:
    CONVERTER_AVAILABLE = False
    IMPORT_ERROR = str(e)


def main():
    """Função principal da aplicação."""

    st.title("Pipeline MD/JSON v3")
    st.markdown("### Conversor Híbrido de Documentos")
    st.markdown("Converte PDF e DOCX para Markdown e JSON estruturado com inferência de schema.")

    if not CONVERTER_AVAILABLE:
        st.error(f"Erro ao importar módulos: {IMPORT_ERROR}")
        st.info("Verifique se todas as dependências estão instaladas: `pip install -r requirements.txt`")
        return

    # Sidebar - Configurações
    with st.sidebar:
        st.header("Configurações")

        st.subheader("Saída")
        generate_markdown = st.checkbox("Gerar Markdown", value=True)
        generate_json = st.checkbox("Gerar JSON", value=True)

        st.subheader("Inferência de Schema")
        enable_schema_inference = st.checkbox(
            "Habilitar inferência de schema",
            value=True,
            help="Usa LLM para inferir estrutura semântica específica do documento"
        )
        include_explanations = st.checkbox(
            "Incluir explicações de campos",
            value=False,
            help="Adiciona explicação de por que cada campo foi incluído"
        )

        st.subheader("Processamento")
        extract_entities = st.checkbox("Extrair entidades", value=True)
        prefer_vision_tables = st.checkbox(
            "Usar visão para tabelas",
            value=False,
            help="Processa tabelas complexas usando Claude Vision"
        )

        st.subheader("Chunks (RAG)")
        chunk_size = st.slider("Tamanho do chunk", 100, 1000, 500)
        chunk_overlap = st.slider("Overlap", 0, 100, 50)

        st.subheader("Markdown")
        include_frontmatter = st.checkbox("Incluir frontmatter YAML", value=True)
        include_toc = st.checkbox("Incluir sumário", value=False)

    # Área principal
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Upload de Documento")

        uploaded_file = st.file_uploader(
            "Escolha um arquivo PDF ou DOCX",
            type=["pdf", "docx", "doc"],
            help="Arraste ou clique para selecionar o arquivo"
        )

        if uploaded_file:
            # Mostrar informações do arquivo
            st.info(f"""
            **Arquivo:** {uploaded_file.name}
            **Tamanho:** {uploaded_file.size / 1024:.1f} KB
            **Tipo:** {uploaded_file.type}
            """)

            # Botão de conversão
            if st.button("Converter Documento", type="primary", use_container_width=True):
                convert_uploaded_file(
                    uploaded_file,
                    ConversionConfig(
                        generate_markdown=generate_markdown,
                        generate_json=generate_json,
                        enable_schema_inference=enable_schema_inference,
                        include_fields_explanation=include_explanations,
                        extract_entities=extract_entities,
                        prefer_vision_for_tables=prefer_vision_tables,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                        include_frontmatter=include_frontmatter,
                        include_toc=include_toc
                    )
                )

    with col2:
        st.subheader("Resultados")

        if "conversion_result" in st.session_state:
            result = st.session_state.conversion_result

            if result.success:
                # Tabs para diferentes visualizações
                tab1, tab2, tab3, tab4 = st.tabs([
                    "Markdown", "JSON", "Entidades", "Info"
                ])

                with tab1:
                    if result.markdown:
                        st.download_button(
                            "Download Markdown",
                            result.markdown,
                            file_name=f"{Path(uploaded_file.name).stem}.md",
                            mime="text/markdown"
                        )
                        with st.expander("Preview", expanded=True):
                            st.markdown(result.markdown[:5000])
                            if len(result.markdown) > 5000:
                                st.info("... (truncado para preview)")

                with tab2:
                    if result.json_data:
                        json_str = json.dumps(result.json_data, indent=2, ensure_ascii=False)
                        st.download_button(
                            "Download JSON",
                            json_str,
                            file_name=f"{Path(uploaded_file.name).stem}.json",
                            mime="application/json"
                        )
                        with st.expander("Preview", expanded=True):
                            # Mostrar structured_data se disponível
                            if "structured_data" in result.json_data:
                                st.markdown("**Tipo de Documento:**")
                                st.code(result.json_data["structured_data"].get("_document_type", "unknown"))

                                st.markdown("**Confiança:**")
                                confidence = result.json_data["structured_data"].get("_confidence", 0)
                                st.progress(confidence)
                                st.text(f"{confidence:.1%}")

                            st.json(result.json_data)

                with tab3:
                    if result.json_data and "entities" in result.json_data:
                        entities = result.json_data["entities"]

                        if entities.get("people"):
                            st.markdown("**Pessoas:**")
                            for p in entities["people"]:
                                role = f" ({p['role']})" if p.get('role') else ""
                                st.markdown(f"- {p['name']}{role}")

                        if entities.get("organizations"):
                            st.markdown("**Organizações:**")
                            for o in entities["organizations"]:
                                st.markdown(f"- {o['name']}")

                        if entities.get("dates"):
                            st.markdown("**Datas:**")
                            for d in entities["dates"]:
                                context = f" - {d['context']}" if d.get('context') else ""
                                st.markdown(f"- {d['original']}{context}")

                        if entities.get("monetary_values"):
                            st.markdown("**Valores Monetários:**")
                            for m in entities["monetary_values"]:
                                context = f" - {m['context']}" if m.get('context') else ""
                                st.markdown(f"- {m['original']}{context}")

                with tab4:
                    if result.json_data and "processing_info" in result.json_data:
                        info = result.json_data["processing_info"]
                        st.markdown(f"""
                        **Pipeline Version:** {info.get('pipeline_version', 'N/A')}

                        **Tempo de Processamento:** {info.get('processing_time_seconds', 0):.2f}s

                        **Tokens Usados:** {info.get('tokens_used', 0):,}

                        **Chamadas de Visão:** {info.get('vision_calls', 0)}

                        **Inferência de Schema:** {'Sim' if info.get('schema_inference_used') else 'Não'}
                        """)

                        if info.get("warnings"):
                            st.warning("Avisos:")
                            for w in info["warnings"]:
                                st.markdown(f"- {w}")

            else:
                st.error("Erro na conversão:")
                for error in result.errors:
                    st.markdown(f"- {error}")


def convert_uploaded_file(uploaded_file, config: ConversionConfig):
    """Converte arquivo uploaded."""

    with st.spinner("Processando documento..."):
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=Path(uploaded_file.name).suffix
        ) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = Path(tmp_file.name)

        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()

        stages = {
            "detection": (0, 5, "Detectando tipo de documento..."),
            "text_extraction": (5, 20, "Extraindo texto..."),
            "structure_analysis": (20, 35, "Analisando estrutura..."),
            "routing": (35, 40, "Roteando por complexidade..."),
            "asset_extraction": (40, 50, "Extraindo assets..."),
            "vision_processing": (50, 65, "Processando com visão..."),
            "synthesis": (65, 70, "Sintetizando documento..."),
            "schema_inference": (70, 80, "Inferindo schema..."),
            "entity_extraction": (80, 85, "Extraindo entidades..."),
            "chunk_generation": (85, 90, "Gerando chunks..."),
            "generation": (90, 100, "Gerando saídas...")
        }

        def progress_callback(stage: str, current: int, total: int):
            if stage in stages:
                start, end, message = stages[stage]
                progress = start + (end - start) * (current / max(total, 1))
                progress_bar.progress(int(progress))
                status_text.text(message)

        try:
            # Configurar diretório de saída temporário
            with tempfile.TemporaryDirectory() as tmp_dir:
                config.output_dir = tmp_dir

                # Converter
                result = convert_document(
                    tmp_path,
                    config=config,
                    progress_callback=progress_callback
                )

                # Salvar resultado no session state
                st.session_state.conversion_result = result

                progress_bar.progress(100)
                status_text.text("Conversão concluída!")

                if result.success:
                    st.success("Documento convertido com sucesso!")
                else:
                    st.error("Falha na conversão")

        except Exception as e:
            st.error(f"Erro: {e}")

        finally:
            # Limpar arquivo temporário
            tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
