"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { Job } from "@/lib/types";

export function useJobPolling(
  jobId: string | null,
  handlers: { onDone?: (job: Job) => void; onError?: (job: Job) => void },
) {
  const [job, setJob] = useState<Job | null>(null);
  const doneRef = useRef(false);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    doneRef.current = false;
    setJob(null);
    if (!jobId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const tick = async () => {
      try {
        const next = await api.getJob(jobId);
        if (cancelled) return;
        setJob(next);
        if (next.status === "succeeded" || next.status === "failed") {
          if (!doneRef.current) {
            doneRef.current = true;
            if (next.status === "succeeded") handlersRef.current.onDone?.(next);
            else handlersRef.current.onError?.(next);
          }
          return;
        }
      } catch {
        /* transient error: keep polling */
      }
      timer = setTimeout(tick, 1100);
    };

    void tick();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobId]);

  return job;
}
