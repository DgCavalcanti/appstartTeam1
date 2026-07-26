import { describe, it, expect, beforeEach, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

import SaaPadroes from '../SaaPadroes.vue';
import api from '../../services/api';

vi.mock('../../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const PANORAMA = {
  pavimentos: [
    {
      id: 1, bloco: 'Bloco E', nome: '2º Pavimento', nome_completo: 'Bloco E — 2º Pavimento',
      padrao_1est: 35, padrao_2est: 8, esp_1est: 11, esp_2est: 3, fechada: 0, capacidade: 68,
    },
    {
      id: 2, bloco: 'Bloco D', nome: '3º Pavimento', nome_completo: 'Bloco D — 3º Pavimento',
      padrao_1est: 9, padrao_2est: 0, esp_1est: 0, esp_2est: 0, fechada: 0, capacidade: 9,
    },
  ],
  capacidade_total: 77,
};

const RESTRICOES = {
  restricoes: [
    { id: 1, unidade: 'CARDIOLOGIA (AMBULATÓRIO)', pavimento_id: 2, pavimento: 'Bloco D — 3º Pavimento', tipo: 'obrigatorio' },
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
    Promise.resolve({ data: url.includes('panorama') ? PANORAMA : RESTRICOES })
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

  it('carrega panorama e restrições ao abrir', async () => {
    const wrapper = await montar();
    expect(api.get).toHaveBeenCalledWith('/api/padroes/panorama');
    expect(api.get).toHaveBeenCalledWith('/api/padroes/restricoes');
    expect(wrapper.text()).toContain('77 estações por turno');
  });

  it('lista as 3 unidades no dropdown, marcando as que não participam', async () => {
    const wrapper = await montar();
    const opcoes = wrapper.find('select').findAll('option').map(o => o.text());
    expect(opcoes).toContain('CARDIOLOGIA (AMBULATÓRIO)');
    expect(opcoes.some(o => o.includes('ALMOXARIFADO') && o.includes('não participa'))).toBe(true);
  });

  it('mostra a restrição padrão existente', async () => {
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
    expect(url).toBe('/api/padroes/panorama');
    expect(body[0]).toMatchObject({ pavimento_id: 1, contagens: { padrao_1est: 37 } });
    expect(wrapper.text()).toContain('79 estações por turno');
  });

  it('adiciona uma restrição padrão', async () => {
    const wrapper = await montar();

    const selects = wrapper.findAll('select');
    await selects[0].setValue('PEDIATRIA (AMBULATÓRIO)'); // clínica
    await selects[1].setValue(1);                          // pavimento

    (api.post as any).mockResolvedValue({
      data: { ...RESTRICOES, restricoes: [...RESTRICOES.restricoes, { id: 2, unidade: 'PEDIATRIA (AMBULATÓRIO)', pavimento_id: 1, pavimento: 'Bloco E — 2º Pavimento', tipo: 'obrigatorio' }] },
    });

    await wrapper.findAll('button').find(b => b.text() === 'Adicionar')!.trigger('click');
    await flushPromises();

    const [url, body] = (api.post as any).mock.calls[0];
    expect(url).toBe('/api/padroes/restricoes');
    expect(body).toMatchObject({ unidade_nome: 'PEDIATRIA (AMBULATÓRIO)', pavimento_catalogo_id: 1, tipo: 'obrigatorio' });
  });

  it('o botão adicionar fica desabilitado sem clínica e pavimento', async () => {
    const wrapper = await montar();
    const botao = () => wrapper.findAll('button').find(b => b.text() === 'Adicionar')!;
    expect(botao().attributes('disabled')).toBeDefined();

    await wrapper.findAll('select')[0].setValue('PEDIATRIA (AMBULATÓRIO)');
    await wrapper.findAll('select')[1].setValue(2);
    expect(botao().attributes('disabled')).toBeUndefined();
  });

  it('remove uma restrição padrão', async () => {
    const wrapper = await montar();
    (api.delete as any).mockResolvedValue({ data: { ...RESTRICOES, restricoes: [] } });

    await wrapper.findAll('button').find(b => b.text() === 'remover')!.trigger('click');
    await flushPromises();

    expect(api.delete).toHaveBeenCalledWith('/api/padroes/restricoes/1');
    expect(wrapper.text()).toContain('Nenhuma restrição padrão');
  });
});
