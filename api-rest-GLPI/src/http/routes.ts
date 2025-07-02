import type { FastifyInstance } from "fastify";

import { login } from "./controllers/login";
import { register } from "./controllers/register";

import { ticketsController } from "./controllers/tickets";
import { categoriesController } from "./controllers/categories";
import { settingsController } from "./controllers/settings";
import { usersController } from "./controllers/users";

export async function routes(app: FastifyInstance) {
  // definindo rotas
  app.post("/sessions", login);
  app.post("/register", register);

  // registrando módulos
  app.register(usersController, { prefix: "/users" });
  app.register(ticketsController, { prefix: "/tickets" });
  app.register(categoriesController, { prefix: "/categories" });
  app.register(settingsController, { prefix: "/settings" });
}
