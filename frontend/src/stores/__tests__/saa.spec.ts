import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useSaaStore } from '@/stores/saa';

describe('SAA Store - Alocação Automática', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('deve executar alocação automática com sucesso', async () => {
    const store = useSaaStore();

    // Dados fictícios
    store.grades = [
      {
        id: 'g1',
        especialidade: 'Cardiologia',
        profissional: 'Dr. João',
        dia_semana: 'Segunda',
        turno: 'Manhã',
        qtd_salas_necessarias: 1,
      },
    ];

    store.salas = [
      {
        id: 's1',
        numero: '101',
        bloco: 'A',
        andar: '1',
        status: 'disponivel',
        acessibilidade: true,
        equipamentos: ['ECG'],
        especialidade_preferencial: 'Cardiologia',
      },
    ];

    // Mock da API
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            alocacoes_criadas: [
              {
                id: 'a1',
                grade_id: 'g1',
                sala_id: 's1',
                dia_semana: 'Segunda',
                turno: 'Manhã',
              },
            ],
            grades_nao_alocadas: [],
            resumo: 'Alocação realizada com sucesso',
          }),
      })
    );

    const resultado = await store.executarAlocacaoAutomatica('Segunda', 'Manhã', 'token-mock');

    expect(resultado.ok).toBe(true);
    expect(resultado.resultado?.alocacoes_criadas.length).toBe(1);
    expect(resultado.resultado?.grades_nao_alocadas.length).toBe(0);
    expect(store.alocacoes.length).toBe(1);
  });

  it('deve retornar erro quando a API falha', async () => {
    const store = useSaaStore();

    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        json: () =>
          Promise.resolve({
            detail: 'Erro na API',
          }),
      })
    );

    const resultado = await store.executarAlocacaoAutomatica('Segunda', 'Manhã', 'token-mock');

    expect(resultado.ok).toBe(false);
    expect(resultado.erro).toBe('Erro na API');
  });

  it('deve detectar conflitos após alocação', async () => {
    const store = useSaaStore();

    store.grades = [
      {
        id: 'g1',
        especialidade: 'Cardiologia',
        profissional: 'Dr. João',
        dia_semana: 'Segunda',
        turno: 'Manhã',
        qtd_salas_necessarias: 1,
      },
    ];

    store.salas = [
      {
        id: 's1',
        numero: '101',
        bloco: 'A',
        andar: '1',
        status: 'reforma',
        acessibilidade: true,
        equipamentos: [],
        especialidade_preferencial: 'Geral',
      },
    ];

    store.alocacoes = [
      {
        id: 'a1',
        grade_id: 'g1',
        sala_id: 's1',
        dia_semana: 'Segunda',
        turno: 'Manhã',
      },
    ];

    expect(store.conflitos.length).toBeGreaterThan(0);
    expect(store.conflitos[0].gravidade).toBe('critico');
  });

  it('deve sincronizar alocações do resultado da API', async () => {
    const store = useSaaStore();

    store.alocacoes = [
      {
        id: 'a-old',
        grade_id: 'g-old',
        sala_id: 's-old',
        dia_semana: 'Segunda',
        turno: 'Manhã',
      },
    ];

    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            alocacoes_criadas: [
              {
                id: 'a1',
                grade_id: 'g1',
                sala_id: 's1',
                dia_semana: 'Segunda',
                turno: 'Manhã',
              },
            ],
            grades_nao_alocadas: [],
            resumo: 'Sucesso',
          }),
      })
    );

    await store.executarAlocacaoAutomatica('Segunda', 'Manhã', 'token-mock');

    // Verifica que alocações antigas foram removidas para o mesmo dia/turno
    const alocacoesSegundaManha = store.alocacoes.filter(
      a => a.dia_semana === 'Segunda' && a.turno === 'Manhã'
    );

    expect(alocacoesSegundaManha.length).toBe(1);
    expect(alocacoesSegundaManha[0].grade_id).toBe('g1');
  });
});
