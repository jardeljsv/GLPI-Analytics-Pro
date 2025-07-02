
import { knex } from "@/database/knex-config";

interface UpdateSettingsParams {
  primary_color?: string;
  secondary_color?: string;
  logo_url?: string;
}

export async function getSettings() {
  const settings = await knex('glpi_settings').first();

  if (!settings) {
    // Se não houver configurações, cria uma com valores padrão
    const [newSettingsId] = await knex('glpi_settings').insert({
      primary_color: '#4EA8DE',
      secondary_color: '#8284FA',
      logo_url: null,
    });
    return knex('glpi_settings').where('id', newSettingsId).first();
  }

  return settings;
}

export async function updateSettings(params: UpdateSettingsParams) {
  const currentSettings = await knex('glpi_settings').first();

  if (!currentSettings) {
    // Se não houver configurações, cria uma nova
    const [newSettingsId] = await knex('glpi_settings').insert({
      primary_color: params.primary_color || '#4EA8DE',
      secondary_color: params.secondary_color || '#8284FA',
      logo_url: params.logo_url || null,
    });
    return knex('glpi_settings').where('id', newSettingsId).first();
  }

  await knex('glpi_settings')
    .where('id', currentSettings.id)
    .update({
      ...params,
      updated_at: knex.fn.now(),
    });

  return knex('glpi_settings').where('id', currentSettings.id).first();
}
