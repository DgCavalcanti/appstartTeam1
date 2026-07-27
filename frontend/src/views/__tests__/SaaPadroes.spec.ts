import { describe, it, expect, beforeEach, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

import SaaPadroes from '../SaaPadroes.vue';
import api from '../../services/api';

vi.mock('../../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

// GET /api/cenarios/padroes
const PANORAMA = {
  pavimentos: [
    {
      id: 1, bloco: 'Bloco E', nome: '2º Pavimento', andar: 2, nome_completo: 'Bloco E — 2º Pavimento',
      padrao_1est: 35, padrao_2est: 8, esp_1est: 11, esp_2est: 3, fechada: 0, capacidade: 68,
    },
    {
      id: 2, bloco: 'Bloco D', nome: '3º Pavimento', andar: 3, nome_completo: 'Bloco D — 3º Pavimento',
      padrao_1est: 9, padrao_2est: 0, esp_1est: 0, esp_2est: 0, fechada: 0, capacidade: 9,
    },
  ],
  capacidade_total: 77,
};

// GET /api/cenarios/regras-padrao
const REGRAS = {
  regras: [
    { id: 1, unidade: 'CARDIOLOGIA (AMBULATÓRIO)', pavimento_catalogo_id: 2, pavimento: 'Bloco D — 3º Pavimento', tipo: 'obrigatorio' },
  ],
  unidades: [
    { nome: 'CARDIOLOGIA (AMBULATÓRIO)', participa_default: true },
    { nome: 'ALMOXARIFADO', participa_default: false },
    { nome: 'PEDIATRIA (AMBULATÓRIO)', participa_default: true },
  ],
  pavimentos: [
    { id: 1, nome_completo: 'Bloco E — 2º Pavimento' },
    { id: 2, nome_completo: 'Bloco D — 3º Pavimento' },
  ],
};

function mockGet() {
  (api.get as any).mockImplementation((url: string) =>
    Promise.resolve({ data: url.includes('regras-padrao') ? REGRAS : PANORAMA })
  );
}

async function montar() {
  mockGet();
  const wrapper = mount(SaaPadroes);
  await flushPromises();
  return wrapper;
}

describe('SaaPadroes.vue', () => {
  beforeEach(() => vi.clearAllMocks());

  it('carrega panorama e regras dos endpoints do backend', async () => {
    const wrapper = await montar();
    expect(api.get).toHaveBeenCalledWith('/api/cenarios/padroes');
    expect(api.get).toHaveBeenCalledWith('/api/cenarios/regras-padrao');
    expect(wrapper.text()).toContain('77 estações por turno');
  });

  it('lista as 3 unidades no dropdown, marcando as que não participam', async () => {
    const wrapper = await montar();
    const opcoes = wrapper.find('select').findAll('option').map(o => o.text());
    expect(opcoes).toContain('CARDIOLOGIA (AMBULATÓRIO)');
    expect(opcoes.some(o => o.includes('ALMOXARIFADO') && o.includes('não participa'))).toBe(true);
  });

  it('mostra a regra padrão existente', async () => {
    const wrapper = await montar();
    expect(wrapper.text()).toContain('CARDIOLOGIA (AMBULATÓRIO)');
    expect(wrapper.text()).toContain('obrigatória');
  });

  it('deriva a capacidade ao editar uma contagem do panorama', async () => {
    const wrapper = await montar();
    (api.put as any).mockResolvedValue({
      data: {
        pavimentos: [
          { ...PANORAMA.pavimentos[0], padrao_1est: 37, capacidade: 70 },
          PANORAMA.pavimentos[1],
        ],
        capacidade_total: 79,
      },
    });

    // Primeiro campo numérico = padrão 1 est. do primeiro pavimento.
    await wrapper.find('table input[type=number]').setValue(37);
    await flushPromises();

    const [url, body] = (api.put as any).mock.calls[0];
    expect(url).toBe('/api/cenarios/padroes');
    expect(body[0]).toMatchObject({ pavimento_id: 1, contagens: { padrao_1est: 37 } });
    expect(wrapper.text()).toContain('79 estações por turno');
  });

  it('adiciona uma regra padrão com o payload do backend', async () => {
    const wrapper = await montar();

    const selects = wrapper.findAll('select');
    await selects[0].setValue('PEDIATRIA (AMBULATÓRIO)'); // clínica
    await selects[1].setValue(1);                          // pavimento

    (api.post as any).mockResolvedValue({
      data: {
        regras: [
          ...REGRAS.regras,
          { id: 2, unidade: 'PEDIATRIA (AMBULATÓRIO)', pavimento_catalogo_id: 1, pavimento: 'Bloco E — 2º Pavimento', tipo: 'obrigatorio' },
        ],
      },
    });

    await wrapper.findAll('button').find(b => b.text() === 'Adicionar')!.trigger('click');
    await flushPromises();

    const [url, body] = (api.post as any).mock.calls[0];
    expect(url).toBe('/api/cenarios/regras-padrao');
    // Campo `unidade` (não `unidade_nome`), como o backend espera.
    expect(body).toMatchObject({ unidade: 'PEDIATRIA (AMBULATÓRIO)', pavimento_catalogo_id: 1, tipo: 'obrigatorio' });
    // A lista da tela é atualizada a partir de `regras`.
    expect(wrapper.text()).toContain('PEDIATRIA (AMBULATÓRIO)');
  });

  it('o botão adicionar fica desabilitado sem clínica e pavimento', async () => {
    const wrapper = await montar();
    const botao = () => wrapper.findAll('button').find(b => b.text() === 'Adicionar')!;
    expect(botao().attributes('disabled')).toBeDefined();

    await wrapper.findAll('select')[0].setValue('PEDIATRIA (AMBULATÓRIO)');
    await wrapper.findAll('select')[1].setValue(2);
    expect(botao().attributes('disabled')).toBeUndefined();
  });

  it('remove uma regra padrão (DELETE devolve só removida)', async () => {
    const wrapper = await montar();
    (api.delete as any).mockResolvedValue({ data: { removida: true } });

    await wrapper.findAll('button').find(b => b.text() === 'remover')!.trigger('click');
    await flushPromises();

    expect(api.delete).toHaveBeenCalledWith('/api/cenarios/regras-padrao/1');
    // A regra sai da lista local, sem depender do corpo do DELETE.
    expect(wrapper.text()).toContain('Nenhuma restrição padrão');
  });
});
