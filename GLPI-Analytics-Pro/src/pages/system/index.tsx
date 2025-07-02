import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useState, useEffect } from 'react';
import { api } from '@/http/api';

interface SettingsData {
  primary_color: string;
  secondary_color: string;
  logo_url: string | null;
}

export const Settings = () => {
  const [settings, setSettings] = useState<SettingsData>({
    primary_color: '#4EA8DE',
    secondary_color: '#8284FA',
    logo_url: null,
  });
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        setLoading(true);
        const response = await api.get('/settings');
        setSettings(response.data as SettingsData);
      } catch (err) {
        setError('Falha ao carregar as configurações.');
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleColorChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setSettings((prev) => ({ ...prev, [name]: value }));
  };

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setLogoFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Atualizar cores
      await api.post('/settings', {
        primary_color: settings.primary_color,
        secondary_color: settings.secondary_color,
      });

      // Upload da logomarca, se houver
      if (logoFile) {
        const formData = new FormData();
        formData.append('logo', logoFile);
        const uploadResponse = await api.post('/settings/logo', formData);
        setSettings((prev) => ({ ...prev, logo_url: (uploadResponse.data as { logo_url: string }).logo_url }));
      }

      setSuccess('Configurações salvas com sucesso!');
    } catch (err) {
      setError('Falha ao salvar as configurações.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full m-24">
      <Card className="max-w-4xl mx-auto p-6 rounded-lg shadow-md card-shadow">
        <CardHeader>
          <CardTitle className="text-2xl font-semibold text-gray-700">Configurações do Sistema</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && <p>Carregando configurações...</p>}
          {error && <p className="text-red-500">{error}</p>}
          {success && <p className="text-green-500">{success}</p>}

          <form onSubmit={handleSubmit} className="space-y-6 mt-6">
            <div>
              <Label htmlFor="primary_color">Cor Primária</Label>
              <Input
                id="primary_color"
                name="primary_color"
                type="color"
                value={settings.primary_color}
                onChange={handleColorChange}
                className="mt-2 w-24 h-12 p-1 border rounded-md"
              />
            </div>

            <div>
              <Label htmlFor="secondary_color">Cor Secundária</Label>
              <Input
                id="secondary_color"
                name="secondary_color"
                type="color"
                value={settings.secondary_color}
                onChange={handleColorChange}
                className="mt-2 w-24 h-12 p-1 border rounded-md"
              />
            </div>

            <div>
              <Label htmlFor="logo_upload">Logomarca</Label>
              <Input
                id="logo_upload"
                name="logo_upload"
                type="file"
                accept="image/*"
                onChange={handleLogoChange}
                className="mt-2"
              />
              {settings.logo_url && (
                <div className="mt-4">
                  <p>Logomarca atual:</p>
                  <img src={settings.logo_url} alt="Logomarca" className="max-h-24 mt-2" />
                </div>
              )}
            </div>

            <Button type="submit" className="w-full bg-green-500 text-white px-4 py-2 rounded" disabled={loading}>
              {loading ? 'Salvando...' : 'Salvar Alterações'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};