import React, { useCallback, useState } from "react";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import { apiErrorMessage } from "../../api/client";
import { CurrencyTotal, DashboardSummary, fetchDashboardSummary } from "../../api/services";
import { contentColumn } from "../../components/ui";
import Icon from "../../components/Icon";
import { colors, layout, radius, spacing, typography } from "../../theme";

/** Tutarları binlik ayraçla, para birimiyle birlikte. */
function formatAmount(row: CurrencyTotal) {
  const amount = row.tutar.toLocaleString("tr-TR", { maximumFractionDigits: 0 });
  return `${amount} ${row.para_birimi}`;
}

/** Para birimi başına bir satır: TRY ile USD toplanamaz, o yüzden tek bir
 *  rakam değil liste gösteriyoruz. */
function CurrencyLines({ rows, tone }: { rows: CurrencyTotal[]; tone?: string }) {
  if (rows.length === 0) return <Text style={styles.emptyValue}>—</Text>;
  return (
    <View>
      {rows.map((row) => (
        <Text key={row.para_birimi} style={[styles.statValue, tone ? { color: tone } : null]}>
          {formatAmount(row)}
          <Text style={styles.statCount}>  ({row.adet})</Text>
        </Text>
      ))}
    </View>
  );
}

function Card({ title, icon, children }: { title: string; icon: any; children: React.ReactNode }) {
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Icon name={icon} size={16} color={colors.primary} />
        <Text style={styles.cardTitle}>{title}</Text>
      </View>
      {children}
    </View>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      {children}
    </View>
  );
}

function Row({ left, right }: { left: string; right: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLeft} numberOfLines={1}>
        {left}
      </Text>
      <Text style={styles.rowRight}>{right}</Text>
    </View>
  );
}

function Bar({ percent, tone }: { percent: number; tone: string }) {
  return (
    <View style={styles.barTrack}>
      <View style={[styles.barFill, { width: `${percent}%`, backgroundColor: tone }]} />
    </View>
  );
}

export default function DashboardScreen() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const load = useCallback((refreshing = false) => {
    if (refreshing) setIsRefreshing(true);
    fetchDashboardSummary()
      .then((summary) => {
        setData(summary);
        setError(null);
      })
      .catch((e) => setError(apiErrorMessage(e)))
      .finally(() => {
        setIsLoading(false);
        setIsRefreshing(false);
      });
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  if (error || !data) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error ?? "Pano yüklenemedi"}</Text>
        <Text style={styles.retry} onPress={() => load()}>
          Tekrar dene
        </Text>
      </View>
    );
  }

  const { faturalar, stok, saha, hedefler } = data;

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={isRefreshing} onRefresh={() => load(true)} tintColor={colors.primary} />
      }
    >
      <Card title="Faturalar" icon="invoice">
        <Stat label="Bu ay kesilen">
          <CurrencyLines rows={faturalar.bu_ay_kesilen} />
        </Stat>
        <Stat label="Vadesi geçen">
          <CurrencyLines rows={faturalar.vadesi_gecen} tone={colors.danger} />
        </Stat>
        <Stat label="7 gün içinde">
          <CurrencyLines rows={faturalar.yaklasan_7_gun} tone={colors.warning} />
        </Stat>
        <Stat label="30 gün içinde">
          <CurrencyLines rows={faturalar.yaklasan_30_gun} />
        </Stat>
        {faturalar.kontrol_gerekli > 0 && (
          <Text style={styles.note}>
            {faturalar.kontrol_gerekli} fatura okunamadı, kontrol gerekiyor
          </Text>
        )}
      </Card>

      <Card title="Stok" icon="stock">
        <View style={styles.tripleRow}>
          <View style={styles.triple}>
            <Text style={styles.bigNumber}>{stok.depoda}</Text>
            <Text style={styles.tripleLabel}>Depoda</Text>
          </View>
          <View style={styles.triple}>
            <Text style={styles.bigNumber}>{stok.hastanelerde_toplam}</Text>
            <Text style={styles.tripleLabel}>Hastanelerde</Text>
          </View>
          <View style={styles.triple}>
            <Text style={styles.bigNumber}>{stok.araclarda_toplam}</Text>
            <Text style={styles.tripleLabel}>Araçlarda</Text>
          </View>
        </View>

        {stok.hastane_dagilimi.length > 0 && (
          <>
            <Text style={styles.subHeading}>Hastane dağılımı</Text>
            {stok.hastane_dagilimi.map((h) => (
              <Row key={h.hastane} left={h.hastane} right={`${h.adet}`} />
            ))}
          </>
        )}

        {stok.arac_dagilimi.length > 0 && (
          <>
            <Text style={styles.subHeading}>Araçlarda</Text>
            {stok.arac_dagilimi.map((v) => (
              <Row key={v.calisan} left={v.calisan} right={`${v.adet}`} />
            ))}
          </>
        )}

        {stok.skt_yaklasan.length > 0 && (
          <>
            <Text style={styles.subHeading}>SKT'si yaklaşanlar</Text>
            {stok.skt_yaklasan.map((s) => (
              <View key={`${s.urun}-${s.lot_no}`} style={styles.expiryRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.rowLeft} numberOfLines={1}>
                    {s.urun}
                  </Text>
                  <Text style={styles.expiryMeta}>
                    Lot {s.lot_no} · {s.konum}
                  </Text>
                </View>
                <Text style={[styles.rowRight, { color: s.kalan_gun <= 30 ? colors.danger : colors.warning }]}>
                  {s.kalan_gun < 0 ? `${-s.kalan_gun} gün geçti` : `${s.kalan_gun} gün`}
                </Text>
              </View>
            ))}
          </>
        )}
      </Card>

      <Card title="Saha (son 7 gün)" icon="location">
        <View style={styles.tripleRow}>
          <View style={styles.triple}>
            <Text style={styles.bigNumber}>{saha.son_7_gun_checkin}</Text>
            <Text style={styles.tripleLabel}>Check-in</Text>
          </View>
          <View style={styles.triple}>
            <Text style={styles.bigNumber}>{saha.ziyaret_edilen_hastane}</Text>
            <Text style={styles.tripleLabel}>Hastane</Text>
          </View>
        </View>
        {saha.calisan_dagilimi.length > 0 ? (
          saha.calisan_dagilimi.map((c) => <Row key={c.calisan} left={c.calisan} right={`${c.adet}`} />)
        ) : (
          <Text style={styles.emptyValue}>Bu hafta check-in yok</Text>
        )}
      </Card>

      <Card title="Hedefler" icon="targets">
        {hedefler.length === 0 ? (
          <Text style={styles.emptyValue}>Süren hedef yok</Text>
        ) : (
          hedefler.map((h) => {
            const tone = h.yuzde >= 100 ? colors.success : h.yuzde >= 50 ? colors.primary : colors.warning;
            return (
              <View key={`${h.baslik}-${h.calisan}`} style={styles.targetRow}>
                <View style={styles.targetHeader}>
                  <Text style={styles.rowLeft} numberOfLines={1}>
                    {h.baslik}
                  </Text>
                  <Text style={[styles.rowRight, { color: tone }]}>
                    {h.ilerleme}/{h.hedef}
                  </Text>
                </View>
                <Bar percent={h.yuzde} tone={tone} />
                <Text style={styles.expiryMeta}>
                  {h.calisan} · {h.kalan_gun} gün kaldı
                </Text>
              </View>
            );
          })
        )}
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: layout.screenPadding, paddingBottom: spacing(4), ...contentColumn },
  center: { flex: 1, backgroundColor: colors.background, alignItems: "center", justifyContent: "center" },
  error: { ...typography.body, color: colors.danger, marginBottom: spacing(1) },
  retry: { ...typography.bodyStrong, color: colors.primary },

  card: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    borderRadius: radius.lg,
    padding: layout.cardPadding,
    marginBottom: layout.cardGap,
  },
  cardHeader: { flexDirection: "row", alignItems: "center", gap: spacing(1), marginBottom: spacing(1.5) },
  cardTitle: { ...typography.cardTitle, color: colors.text },

  stat: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    paddingVertical: spacing(0.75),
  },
  statLabel: { ...typography.body, color: colors.textMuted },
  statValue: { ...typography.bodyStrong, color: colors.text, textAlign: "right" },
  statCount: { ...typography.meta, color: colors.textDim },
  emptyValue: { ...typography.body, color: colors.textDim },
  note: { ...typography.meta, color: colors.warning, marginTop: spacing(1) },

  tripleRow: { flexDirection: "row", marginBottom: spacing(1) },
  triple: { flex: 1, alignItems: "center" },
  bigNumber: { fontSize: 24, fontWeight: "700", color: colors.text },
  tripleLabel: { ...typography.meta, color: colors.textMuted },

  subHeading: {
    ...typography.meta,
    color: colors.textDim,
    textTransform: "uppercase",
    marginTop: spacing(1.5),
    marginBottom: spacing(0.5),
  },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing(0.5), gap: spacing(1) },
  rowLeft: { ...typography.body, color: colors.text, flex: 1 },
  rowRight: { ...typography.bodyStrong, color: colors.text },

  expiryRow: { flexDirection: "row", alignItems: "center", paddingVertical: spacing(0.75), gap: spacing(1) },
  expiryMeta: { ...typography.meta, color: colors.textDim },

  targetRow: { paddingVertical: spacing(0.75) },
  targetHeader: { flexDirection: "row", justifyContent: "space-between", gap: spacing(1) },
  barTrack: {
    height: 6,
    borderRadius: radius.full,
    backgroundColor: colors.surfaceAlt,
    marginVertical: spacing(0.5),
    overflow: "hidden",
  },
  barFill: { height: "100%", borderRadius: radius.full },
});
