from app.core.database import SessionLocal
from app.repositories.projects import get_by_slug
from app.schemas.project import ProjectForm
from app.services.projects import create_project


def main() -> None:
    with SessionLocal() as db:
        if get_by_slug(db, "rennam-semantic-docs"):
            print("Projeto inicial já existe.")
            return
        form = ProjectForm(
            title="Rennam Semantic Docs",
            slug="rennam-semantic-docs",
            summary=(
                "Busca semântica em documentos com embeddings e banco vetorial, "
                "evoluindo depois para respostas com fontes."
            ),
            problem=(
                "Buscas por palavras-chave falham quando a pergunta e o documento "
                "usam termos diferentes para expressar a mesma ideia."
            ),
            solution=(
                "Construir primeiro um pipeline de ingestão, chunking, embeddings e "
                "recuperação por similaridade. A geração com LLM entra apenas na "
                "segunda etapa."
            ),
            architecture=(
                "Upload → extração e limpeza → chunks → embeddings → pgvector → "
                "busca por similaridade → trechos relevantes."
            ),
            decisions=(
                "- PostgreSQL + pgvector para manter metadados relacionais e vetores.\n"
                "- FastAPI para expor ingestão e consulta.\n"
                "- Avaliação de recuperação antes de adicionar o LLM."
            ),
            results="Projeto planejado. Métricas serão adicionadas após o MVP.",
            learnings=(
                "O estudo de caso registrará qualidade de recuperação, latência, "
                "estratégia de chunking e limitações encontradas."
            ),
            course="DSA — Embeddings e Bancos Vetoriais",
            status="planned",
            visibility="published",
            featured=True,
            technologies="Python, FastAPI, PostgreSQL, pgvector, Embeddings",
            seo_description=(
                "Projeto de busca semântica em documentos com embeddings, FastAPI, "
                "PostgreSQL e pgvector."
            ),
        )
        create_project(db, form)
        print("Projeto inicial criado.")


if __name__ == "__main__":
    main()
