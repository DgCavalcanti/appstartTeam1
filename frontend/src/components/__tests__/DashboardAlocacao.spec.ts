import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import DashboardAlocacao from '@/components/DashboardAlocacao.vue';

describe('DashboardAlocacao.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia());

    // Mock localStorage
    Storage.prototype.getItem = vi.fn((key) => {
      if (key === 'token') return 'test-token';
      return null;
    });

    // Mock fetch
    global.fetch = vi.fn();
  });

  it('deve renderizar o formulário de alocação', () => {
    const wrapper = mount(DashboardAlocacao, {
      global: {
        stubs: {
          // Stub para componentes que não precisam ser testados
        },
      },
    });

    expect(wrapper.find('h1').text()).toContain('Dashboard de Alocação Automática');
    expect(wrapper.find('select#dia').exists()).toBe(true);
    expect(wrapper.find('select#turno').exists()).toBe(true);
    expect(wrapper.find('button.botao-executar').exists()).toBe(true);
  });

  it('deve desabilitar botão quando dia/turno não são selecionados', async () => {
    const wrapper = mount(DashboardAlocacao, {
      global: {
        stubs: {},
      },
    });

    const botao = wrapper.find('button.botao-executar');
    expect(botao.attributes('disabled')).toBeDefined();
  });

  it('deve habilitar botão quando dia e turno são selecionados', async () => {
    const wrapper = mount(DashboardAlocacao);

    const selectDia = wrapper.find('select#dia');
    const selectTurno = wrapper.find('select#turno');

    await selectDia.setValue('Segunda');
    await selectTurno.setValue('Manhã');

    const botao = wrapper.find('button.botao-executar');
    expect(botao.attributes('disabled')).toBeUndefined();
  });

  it('deve exibir erro quando autenticação falhar', async () => {
    Storage.prototype.getItem = vi.fn(() => null);

    const wrapper = mount(DashboardAlocacao);

    const selectDia = wrapper.find('select#dia');
    const selectTurno = wrapper.find('select#turno');

    await selectDia.setValue('Segunda');
    await selectTurno.setValue('Manhã');

    const botao = wrapper.find('button.botao-executar');
    await botao.trigger('click');

    expect(wrapper.text()).toContain('Token de autenticação não encontrado');
  });

  it('deve exibir resultado após sucesso', async () => {
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

    const wrapper = mount(DashboardAlocacao);

    const selectDia = wrapper.find('select#dia');
    const selectTurno = wrapper.find('select#turno');

    await selectDia.setValue('Segunda');
    await selectTurno.setValue('Manhã');

    const botao = wrapper.find('button.botao-executar');
    await botao.trigger('click');

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('Resultado da Alocação');
  });
});
