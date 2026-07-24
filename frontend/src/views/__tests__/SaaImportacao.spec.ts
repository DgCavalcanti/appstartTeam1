import { describe, it, expect, beforeEach, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

import SaaImportacao from '../SaaImportacao.vue';
import api from '../../services/api';

vi.mock('../../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

const PADROES = {
  pavimentos: [
    {
      bloco: 'Bloco A', nome: 'Térreo', nome_completo: 'Bloco A — Térreo',
      padrao_1est: 8, padrao_2est: 9, esp_1est: 4, esp_2est: 2, fechada: 0,
      capacidade: 34,
    },
    {
      bloco: 'Bloco B', nome: 'Térreo', nome_completo: 'Bloco B — Térreo',
      padrao_1est: 9, padrao_2est: 8, esp_1est: 2, esp_2est: 2, fechada: 1,
      capacidade: 31,
    },
  ],
  turnos: [
    { dia: 'segunda', periodo: 'manha' }, { dia: 'segunda', periodo: 'tarde' },
    { dia: 'terca', periodo: 'manha' }, { dia: 'terca', periodo: 'tarde' },
    { dia: 'quarta', periodo: 'manha' }, { dia: 'quarta', periodo: 'tarde' },
    { dia: 'quinta', periodo: 'manha' }, { dia: 'quinta', periodo: 'tarde' },
    { dia: 'sexta', periodo: 'manha' }, { dia: 'sexta', periodo: 'tarde' },
  ],
  unidades_excluidas: [],
};

const demanda = (q: number) => Array.from({ length: 10 }, () => q);

const IMPORTACAO = {
  arquivo: 'vw_grades.csv',
  turnos: PADROES.turnos,
  relatorio: {
    linhas_brutas: 5695, linhas_apos_filtros: 2603,
    total_slots: 1420, total_demandas: 334,
    percentual_apos_filtros: 45.7, percentual_slots: 24.9, percentual_demandas: 5.9,
    descartadas_por_situacao: 1200, descartadas_por_condicao: 900,
    descartadas_por_unidade: 950, descartadas_por_dia: 21,
    descartadas_por_noite: 59, slots_em_revisao: 7,
  },
  // O backend devolve todas as unidades vistas, com a participação padrão do
  // catálogo: CARDIOLOGIA participa; ALMOXARIFADO não.
  unidades: [
    { nome: 'ALMOXARIFADO', participa: false, nova: false },
    { nome: 'CARDIOLOGIA (AMBULATÓRIO)', participa: true, nova: false },
  ],
  clinicas: [
    { id: 1, nome: 'CARDIOLOGIA (AMBULATÓRIO)', demanda: demanda(3), total: 30, pico: 3 },
  ],
  unidades_novas: [],
  slots_em_revisao: [],
  alocacao: {
    total_alocado: 40,
    total_nao_alocado: 0,
    por_clinica: [
      {
        clinica_id: 1, nome: 'CARDIOLOGIA (AMBULATÓRIO)', pavimento_id: 1,
        pavimento: 'Bloco A — Térreo', alocado: demanda(3), nao_alocado: demanda(0),
        total_alocado: 30, total_nao_alocado: 0,
      },
      {
        clinica_id: 2, nome: 'ALMOXARIFADO', pavimento_id: 2,
        pavimento: 'Bloco B — Térreo', alocado: demanda(1), nao_alocado: demanda(0),
        total_alocado: 10, total_nao_alocado: 0,
      },
    ],
    por_pavimento: [
      {
        pavimento_id: 1, nome: 'Bloco A — Térreo', capacidade: 34,
        ocupacao: demanda(3), demanda: demanda(3),
        ocupacao_media: 8.8, ocupacao_pico: 8.8, clinicas: 1,
      },
      {
        pavimento_id: 2, nome: 'Bloco B — Térreo', capacidade: 31,
        ocupacao: demanda(1), demanda: demanda(1),
        ocupacao_media: 3.2, ocupacao_pico: 3.2, clinicas: 1,
      },
    ],
  },
};

function arquivoFalso() {
  return new File(['Grade,Profissional_Grade\n1,Dr. A'], 'vw_grades.csv', {
    type: 'text/csv',
  });
}

/** Monta a tela e roda uma importação, deixando o resultado na tela. */
async function montarComResultado(cenarios: unknown[] = []) {
  (api.get as any).mockImplementation((url: string) =>
    Promise.resolve({ data: url.includes('padroes') ? PADROES : cenarios })
  );
  (api.post as any).mockResolvedValue({ data: IMPORTACAO });

  const wrapper = mount(SaaImportacao);
  await flushPromises();

  const input = wrapper.find('input[type=file]');
  Object.defineProperty(input.element, 'files', { value: [arquivoFalso()] });
  await input.trigger('change');

  const botao = wrapper
    .findAll('button')
    .find(b => b.text().includes('Importar e alocar'))!;
  await botao.trigger('click');
  await flushPromises();

  return wrapper;
}

describe('SaaImportacao.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('parte da área de envio, sem resultado na tela', async () => {
    (api.get as any).mockResolvedValue({ data: [] });

    const wrapper = mount(SaaImportacao);
    await flushPromises();

    expect(wrapper.text()).toContain('Etapa 1 — Importação');
    expect(wrapper.find('input[type=file]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Redução dos dados');
  });

  it('busca o histórico ao abrir', async () => {
    (api.get as any).mockResolvedValue({ data: [] });

    mount(SaaImportacao);
    await flushPromises();

    expect(api.get).toHaveBeenCalledWith('/api/cenarios');
  });

  it('mostra a redução e os descartes por motivo', async () => {
    const wrapper = await montarComResultado();
    const texto = wrapper.text();

    expect(texto).toContain('Redução dos dados');
    expect(texto).toContain('5.695');
    expect(texto).toContain('Turno Noite');
    expect(texto).toContain('59');
  });

  it('deriva a capacidade das contagens de salas', async () => {
    const wrapper = await montarComResultado();

    // Bloco A: 8 + 2×9 + 4 + 2×2 = 34 | Bloco B: 9 + 2×8 + 2 + 2×2 = 31
    expect(wrapper.text()).toContain('65 estações por turno');
  });

  it('recalcula a capacidade quando o gestor edita uma contagem', async () => {
    const wrapper = await montarComResultado();

    // O segundo campo do primeiro pavimento é "Padrão 2 est.": cada sala vale 2.
    const campos = wrapper.findAll('input[type=number]');
    await campos[1].setValue(14);

    expect(wrapper.text()).toContain('75 estações por turno');
  });

  it('marca a participação de cada unidade pelo padrão do catálogo', async () => {
    const wrapper = await montarComResultado();

    const marcadas = wrapper
      .findAll('input[type=checkbox]')
      .filter(c => (c.element as HTMLInputElement).checked)
      .map(c => (c.element as HTMLInputElement).value);

    // Só CARDIOLOGIA vem marcada; ALMOXARIFADO não participa, por catálogo.
    expect(marcadas).toEqual(['CARDIOLOGIA (AMBULATÓRIO)']);
  });

  it('a primeira importação não envia exclusões — deixa o catálogo decidir', async () => {
    await montarComResultado();

    const [, form] = (api.post as any).mock.calls.at(-1);
    // Sem unidades_excluidas: o backend aplica a lista do ambulatório.
    expect(form.get('unidades_excluidas')).toBeNull();
  });

  it('reprocessar envia a seleção ajustada do gestor', async () => {
    const wrapper = await montarComResultado();

    // O gestor re-inclui ALMOXARIFADO.
    const almox = wrapper
      .findAll('input[type=checkbox]')
      .find(c => (c.element as HTMLInputElement).value === 'ALMOXARIFADO')!;
    await almox.setValue(true);

    (api.post as any).mockClear();
    await wrapper.findAll('button').find(b => b.text() === 'Reprocessar')!.trigger('click');
    await flushPromises();

    const [url, form] = (api.post as any).mock.calls[0];
    expect(url).toBe('/api/importacao');
    // Agora manda exclusões explícitas — e nenhuma unidade está de fora.
    expect(JSON.parse(form.get('unidades_excluidas'))).toEqual([]);
  });

  it('só habilita o salvamento depois de nomear o cenário', async () => {
    const wrapper = await montarComResultado();

    const botao = () =>
      wrapper.findAll('button').find(b => b.text().startsWith('Salvar cenário'))!;
    expect(botao().attributes('disabled')).toBeDefined();

    const campo = wrapper.findAll('input').find(i => i.attributes('placeholder')?.includes('proposta'))!;
    await campo.setValue('Proposta 1');

    expect(botao().attributes('disabled')).toBeUndefined();
  });

  it('salva o cenário com a seleção confirmada na tela', async () => {
    const wrapper = await montarComResultado();

    const campo = wrapper.findAll('input').find(i => i.attributes('placeholder')?.includes('proposta'))!;
    await campo.setValue('Proposta 1');

    (api.post as any).mockClear();
    (api.post as any).mockResolvedValue({ data: { id: 1 } });

    await wrapper.findAll('button').find(b => b.text().startsWith('Salvar cenário'))!.trigger('click');
    await flushPromises();

    const [url, form] = (api.post as any).mock.calls[0];
    expect(url).toBe('/api/cenarios');
    expect(form.get('nome')).toBe('Proposta 1');
    // ALMOXARIFADO ficou desmarcado (padrão do catálogo) → vai como exclusão.
    expect(JSON.parse(form.get('unidades_excluidas'))).toEqual(['ALMOXARIFADO']);
  });

  it('mostra o histórico e identifica os clones', async () => {
    const wrapper = await montarComResultado([
      {
        id: 2, nome: 'Proposta 1 (cópia)', status: 'rascunho', etapa_atual: 1,
        criado_em: '2026-07-24T01:49:00', origem_id: 1, unidades: 40, pavimentos: 9,
      },
    ]);

    expect(wrapper.text()).toContain('Histórico (1)');
    expect(wrapper.text()).toContain('clone de #1');
  });

  it('exibe a mensagem de erro devolvida pela API', async () => {
    (api.get as any).mockImplementation((url: string) =>
      Promise.resolve({ data: url.includes('padroes') ? PADROES : [] })
    );
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'extensão não suportada: .txt' } },
    });

    const wrapper = mount(SaaImportacao);
    await flushPromises();

    const input = wrapper.find('input[type=file]');
    Object.defineProperty(input.element, 'files', { value: [arquivoFalso()] });
    await input.trigger('change');
    await wrapper.findAll('button').find(b => b.text().includes('Importar e alocar'))!.trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('extensão não suportada: .txt');
  });
});
