export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.18"
  }
  public: {
    Tables: {
      prediction_ledger: {
        Row: {
          claim: string
          claim_key: string | null
          created_at: string
          evidence_snapshot: Json
          horizon_end: string
          horizon_start: string
          id: string
          information_cutoff: string
          locked: boolean
          model_version: string | null
          probability: number
          profile_id: string | null
          user_id: string
          validation_rule: Json
        }
        Insert: {
          claim: string
          claim_key?: string | null
          created_at?: string
          evidence_snapshot: Json
          horizon_end: string
          horizon_start: string
          id?: string
          information_cutoff: string
          locked?: boolean
          model_version?: string | null
          probability: number
          profile_id?: string | null
          user_id: string
          validation_rule: Json
        }
        Update: {
          claim?: string
          claim_key?: string | null
          created_at?: string
          evidence_snapshot?: Json
          horizon_end?: string
          horizon_start?: string
          id?: string
          information_cutoff?: string
          locked?: boolean
          model_version?: string | null
          probability?: number
          profile_id?: string | null
          user_id?: string
          validation_rule?: Json
        }
        Relationships: [
          {
            foreignKeyName: "prediction_ledger_profile_id_fkey"
            columns: ["profile_id"]
            isOneToOne: false
            referencedRelation: "user_profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      user_profiles: {
        Row: {
          birth_date: string
          birth_lat: number | null
          birth_lng: number | null
          birth_place_label: string | null
          birth_time: string | null
          birth_time_known: boolean
          created_at: string
          display_name: string | null
          id: string
          updated_at: string
          user_id: string
        }
        Insert: {
          birth_date: string
          birth_lat?: number | null
          birth_lng?: number | null
          birth_place_label?: string | null
          birth_time?: string | null
          birth_time_known?: boolean
          created_at?: string
          display_name?: string | null
          id?: string
          updated_at?: string
          user_id: string
        }
        Update: {
          birth_date?: string
          birth_lat?: number | null
          birth_lng?: number | null
          birth_place_label?: string | null
          birth_time?: string | null
          birth_time_known?: boolean
          created_at?: string
          display_name?: string | null
          id?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      lifegraph_dataset_status_v1: {
        Row: {
          created_at: string | null
          dataset_key: string | null
          db_events: number | null
          db_people: number | null
          db_year_states: number | null
          event_count: number | null
          model_ready_thick_people: number | null
          person_count: number | null
          status: string | null
          version: string | null
        }
        Insert: {
          created_at?: string | null
          dataset_key?: string | null
          db_events?: never
          db_people?: never
          db_year_states?: never
          event_count?: number | null
          model_ready_thick_people?: never
          person_count?: number | null
          status?: string | null
          version?: string | null
        }
        Update: {
          created_at?: string | null
          dataset_key?: string | null
          db_events?: never
          db_people?: never
          db_year_states?: never
          event_count?: number | null
          model_ready_thick_people?: never
          person_count?: number | null
          status?: string | null
          version?: string | null
        }
        Relationships: []
      }
      lifegraph_events_v1: {
        Row: {
          age_max: number | null
          age_mid: number | null
          age_min: number | null
          attributes: Json | null
          canonical_name: string | null
          confidence: number | null
          domain: string | null
          event_date_max: string | null
          event_date_min: string | null
          event_key: string | null
          event_type: string | null
          id: number | null
          model_eligible: boolean | null
          observable_from: string | null
          quality_flags: Json | null
          source_family: string | null
          source_url: string | null
          temporal_precision: string | null
          wikidata_id: string | null
        }
        Relationships: []
      }
      lifegraph_model_eligibility_v1: {
        Row: {
          any_trajectory_task: boolean | null
          canonical_name: string | null
          documentation_density: string | null
          domain_count: number | null
          hazard_task: boolean | null
          multisource_validation_task: boolean | null
          next_event_task: boolean | null
          observed_life_stage_count: number | null
          person_id: number | null
          raw_event_count: number | null
          sequence_task: boolean | null
          source_family_count: number | null
          strict_dense_benchmark: boolean | null
          trajectory_event_count: number | null
          wikidata_id: string | null
        }
        Relationships: []
      }
      lifegraph_model_inputs_v1: {
        Row: {
          birth_country: string | null
          birth_date: string | null
          birth_place: string | null
          birth_reliability: string | null
          birth_time: string | null
          birth_time_known: boolean | null
          canonical_name: string | null
          feature_version: string | null
          four_pillars: Json | null
          gender: string | null
          latitude: number | null
          longitude: number | null
          objective_features: Json | null
          person_id: number | null
          quality_flags: Json | null
          wikidata_id: string | null
        }
        Relationships: []
      }
      lifegraph_observation_profiles_v1: {
        Row: {
          birth_overlap_events: number | null
          canonical_name: string | null
          day_precision_events: number | null
          documentation_density: string | null
          domain_count: number | null
          first_recorded_event_date: string | null
          first_trajectory_event_age: number | null
          high_confidence_events: number | null
          last_recorded_event_date: string | null
          last_trajectory_event_age: number | null
          month_precision_events: number | null
          multi_domain: boolean | null
          multi_source: boolean | null
          multi_stage: boolean | null
          observed_life_stage_count: number | null
          person_id: number | null
          posthumous_events: number | null
          prebirth_interval_events: number | null
          raw_event_count: number | null
          source_event_counts: Json | null
          source_family_count: number | null
          trajectory_event_count: number | null
          wikidata_id: string | null
          year_precision_events: number | null
        }
        Relationships: []
      }
      lifegraph_people_v1: {
        Row: {
          bazi_feature_version: string | null
          birth_country: string | null
          birth_date: string | null
          birth_place: string | null
          birth_reliability: string | null
          birth_time: string | null
          birth_time_known: boolean | null
          canonical_name: string | null
          domain_count: number | null
          event_count: number | null
          four_pillars: Json | null
          gender: string | null
          id: number | null
          life_stage_count: number | null
          model_ready_thick: boolean | null
          source_family_count: number | null
          wikidata_id: string | null
        }
        Relationships: []
      }
      lifegraph_training_examples_v1: {
        Row: {
          canonical_name: string | null
          censoring_reason: string | null
          cutoff_age: number | null
          cutoff_date: string | null
          cutoff_features: Json | null
          dataset_key: string | null
          dataset_status: string | null
          dataset_version: string | null
          eligibility_flags: Json | null
          fingerprint_sha256: string | null
          history_domain_count: number | null
          history_event_count: number | null
          history_life_stage_count: number | null
          history_source_family_count: number | null
          history_summary: Json | null
          included_event_keys: string[] | null
          information_cutoff: string | null
          leakage_audit_passed: boolean | null
          observation_end_date: string | null
          person_hash_fold: number | null
          person_hash_split: string | null
          right_censored: boolean | null
          target_age: number | null
          target_class_4: string | null
          target_domain_raw: string | null
          target_event_type: string | null
          target_observable_from: string | null
          target_payload: Json | null
          wikidata_id: string | null
        }
        Relationships: []
      }
      lifegraph_training_readiness_v1: {
        Row: {
          dataset_key: string | null
          error_audit_count: number | null
          failed_error_audits: number | null
          fingerprint_sha256: string | null
          id: string | null
          metadata: Json | null
          person_count: number | null
          row_count: number | null
          status: string | null
          training_ready: boolean | null
          version: string | null
          warning_count: number | null
        }
        Relationships: []
      }
      lifegraph_training_splits_v1: {
        Row: {
          assignment_basis: Json | null
          dataset_key: string | null
          dataset_version: string | null
          fold: number | null
          scenario_key: string | null
          split_group: string | null
          split_name: string | null
          wikidata_id: string | null
        }
        Relationships: []
      }
      lifegraph_year_states_v1: {
        Row: {
          canonical_name: string | null
          id: number | null
          information_cutoff: string | null
          state: Json | null
          state_spec_version: string | null
          wikidata_id: string | null
          year: number | null
        }
        Relationships: []
      }
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
