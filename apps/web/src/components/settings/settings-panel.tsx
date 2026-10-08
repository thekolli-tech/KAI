"use client";

import { kaiConfig } from "@kai/config";
import { brand } from "@kai/shared";

import { Modal } from "@/components/kai/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function SettingsPanel() {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-8 px-5 py-10 md:px-8">
      <header className="grid gap-2">
        <p className="text-[11px] tracking-[0.22em] text-gold uppercase">Settings</p>
        <h1 className="font-display text-4xl">Local workspace</h1>
        <p className="text-sm leading-6 text-muted-foreground">
          {brand.name} phase {kaiConfig.phase} is running without accounts. Configuration lives in
          environment variables on the server.
        </p>
      </header>
      <div className="grid gap-2">
        <label htmlFor="display-name" className="text-sm text-foreground">
          Display name
        </label>
        <Input
          id="display-name"
          disabled
          placeholder="Display name"
          aria-describedby="display-name-note"
        />
        <p id="display-name-note" className="text-xs text-muted-foreground">
          Accounts are not enabled. This field is not saved.
        </p>
      </div>
      <Modal
        title="What this phase includes"
        description="The workspace sends messages through the local mock runtime. This page does not save an account."
        trigger={<Button variant="outline">Phase scope</Button>}
      >
        <ul className="grid gap-2 text-sm text-muted-foreground">
          <li>The web workspace and the API health check are running.</li>
          <li>The composer streams from the local mock runtime. It is not a production model.</li>
          <li>The browser does not receive the local bearer token.</li>
          <li>Transcripts stay in this workspace process. They are not written to the database.</li>
          <li>Tools, agents, memory, and documents are not running.</li>
          <li>No hosted model provider is connected.</li>
        </ul>
      </Modal>
    </div>
  );
}
