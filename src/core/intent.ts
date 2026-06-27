export type Intent = "projeto" | "treino" | "livre";

export function intentClause(intent: Intent | undefined): string {
  switch (intent) {
    case "projeto":
      return "O aluno trabalha num PROJETO real: valorize estrutura, organização e manutenção.";
    case "treino":
      return "O aluno está em TREINO: foque em fundamentos e no idioma correto, bem fundamentado.";
    case "livre":
      return "O aluno explora LIVREMENTE: seja leve, comente só o essencial.";
    default:
      return "";
  }
}
