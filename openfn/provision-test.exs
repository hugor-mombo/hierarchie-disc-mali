# Run via Lightning RPC after copying this file, connection-test.js and the private
# registry credential into /tmp of the web container. Never prints credential data.
alias Lightning.{Repo,Projects,Credentials,Workflows}
alias Lightning.Projects.Project
alias Lightning.Credentials.Credential
alias Lightning.Projects.ProjectCredential
alias Lightning.Workflows.Workflow
user = Repo.get_by!(Lightning.Accounts.User, email: "hmombo@musohealth.org")
metadata_path = "/tmp/registry-test-metadata.json"
existing_project = if File.exists?(metadata_path) do
  metadata = Jason.decode!(File.read!(metadata_path))
  Repo.get(Project, metadata["projectId"])
end
project = existing_project || Repo.get_by(Project, name: "disc-mali-recette") ||
  case Projects.create_project(%{name: "disc-mali-recette", description: "Recette des correspondances et de l'audit, sans envoi DHIS2", env: "main", project_users: [%{user_id: user.id, role: :owner}]}, false) do
    {:ok, item} -> item
    _ -> raise "PROJECT_CREATION_FAILED"
  end
credential = Repo.get_by(Credential, name: "Registre DISC - recette", user_id: user.id) ||
  case Credentials.create_credential(%{name: "Registre DISC - recette", user_id: user.id, schema: "raw",
    credential_bodies: [%{name: "main", body: Jason.decode!(File.read!("/tmp/registry.credential.json"))}],
    project_credentials: [%{project_id: project.id}]}) do
    {:ok, item} -> item
    _ -> raise "CREDENTIAL_CREATION_FAILED"
  end
pc = Repo.get_by!(ProjectCredential, project_id: project.id, credential_id: credential.id)
workflow = Repo.get_by(Workflow, project_id: project.id, name: "Connexion registre et audit - TEST") ||
  (fn ->
    trigger_id = Ecto.UUID.generate()
    job_id = Ecto.UUID.generate()
    attrs = %{name: "Connexion registre et audit - TEST", project_id: project.id,
      jobs: [%{id: job_id, name: "Lire le mapping et journaliser une simulation", adaptor: "@openfn/language-http@7.2.3", project_credential_id: pc.id, body: File.read!("/tmp/connection-test.js")}],
      triggers: [%{id: trigger_id, type: :webhook, enabled: false}],
      edges: [%{id: Ecto.UUID.generate(), source_trigger_id: trigger_id, target_job_id: job_id, condition_type: :always, enabled: true}]}
    case Workflows.save_workflow(attrs, user) do
      {:ok, item} -> item
      _ -> raise "WORKFLOW_CREATION_FAILED"
    end
  end).()
workflow = Repo.preload(workflow, [:jobs, :edges, :triggers])
job = List.first(workflow.jobs)
body = File.read!("/tmp/connection-test.js")
workflow = if job.body != body do
  case Workflows.save_workflow(Workflows.change_workflow(workflow, %{jobs: [%{id: job.id, body: body}]}), user) do
    {:ok, item} -> item
    _ -> raise "TEST_WORKFLOW_UPDATE_FAILED"
  end
else
  workflow
end
trigger = Repo.preload(workflow, :triggers).triggers |> List.first()
File.write!("/tmp/registry-test-metadata.json", Jason.encode!(%{projectId: project.id, workflowId: workflow.id, triggerId: trigger.id}))
IO.puts("Projet de recette et workflow créés ; déclencheur public désactivé.")
