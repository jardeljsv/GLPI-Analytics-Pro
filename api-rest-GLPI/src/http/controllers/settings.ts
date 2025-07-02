
import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { verifyJwt } from "../middlewares/verify-jwt";
import { getSettings, updateSettings } from "@/use-cases/settings";

export async function settingsController(app: FastifyInstance) {
  app.get("/", { onRequest: [verifyJwt] }, async (_, reply) => {
    const settings = await getSettings();
    return reply.status(200).send(settings);
  });

  app.post("/", { onRequest: [verifyJwt] }, async (req, reply) => {
    const updateSettingsBodySchema = z.object({
      primary_color: z.string().optional(),
      secondary_color: z.string().optional(),
      logo_url: z.string().nullable().optional(),
    });

    const { primary_color, secondary_color, logo_url } = updateSettingsBodySchema.parse(req.body);

    const updatedSettings = await updateSettings({
      primary_color,
      secondary_color,
      logo_url,
    });

    return reply.status(200).send(updatedSettings);
  });
}
