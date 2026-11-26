// Railway settings for the app's service. Railway reads them from its own copy: after changing this file,
// run `railway config plan` and `railway config apply` (see "Railway's settings" in DEPLOYMENT_GUIDE.md).
import { defineRailway, github, project, service } from "railway/iac";
// This repository manages only its own resources in the environment. Other
// repositories export their own partial name.
// See https://docs.railway.com/infrastructure-as-code#multi-repo-projects
export const partial = "moodforecast_ai";
export default defineRailway(() => {
  const moodforecast_ai = service("moodforecast_ai", {
    source: github("KathFK1234/moodforecast_ai", { branch: "main", checkSuites: false, rootDirectory: "/backend" }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE" },
    start: "sh -c 'exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-graceful-shutdown 10'",
    healthcheck: "/health",
    healthcheckTimeout: 60,
    // Time to finish after the stop signal, a little longer than uvicorn's own 10 s limit
    deploy: { drainingSeconds: 15 },
    replicas: { "europe-west4-drams3a": 1 },
    networking: { privateNetworkEndpoint: "moodforecastai" },
  });

  return project("MoodForecastAI", {
    variables: { managed: false },
    resources: [moodforecast_ai],
  });
});
