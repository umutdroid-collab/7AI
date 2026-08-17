import React, { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Linking,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import Alert from "../../utils/alert";
import * as DocumentPicker from "expo-document-picker";
import { askAssistant, fetchClinicalDocuments, uploadClinicalDocument } from "../../api/services";
import { ChatMessage } from "../../types";
import { colors, layout, radius, spacing, typography } from "../../theme";
import { contentColumn } from "../../components/ui";
import Icon from "../../components/Icon";
import { apiErrorMessage } from "../../api/client";
import { useAuth } from "../../context/AuthContext";

const WELCOME: ChatMessage = {
  id: "welcome",
  role: "assistant",
  text:
    "Merhaba, ben klinik literatür asistanınızım. Ürünlerimiz ve ilgili hastalıklar hakkında sorularınızı, " +
    "klinik çalışma klasörümüzdeki dokümanlara ve PubMed'deki güncel yayınlara dayanarak, kaynak göstererek " +
    "cevaplıyorum. Konu dışı sorulara cevap veremem.",
};

export default function AssistantChatScreen() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [documentCount, setDocumentCount] = useState<number | null>(null);
  const listRef = useRef<FlatList>(null);

  const loadDocumentCount = useCallback(() => {
    fetchClinicalDocuments()
      .then((docs) => setDocumentCount(docs.length))
      .catch(() => {});
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadDocumentCount();
    }, [loadDocumentCount])
  );

  async function handleUploadDocument() {
    const result = await DocumentPicker.getDocumentAsync({ type: "application/pdf", copyToCacheDirectory: true });
    if (result.canceled || !result.assets?.length) return;

    const file = result.assets[0];
    setIsUploading(true);
    try {
      await uploadClinicalDocument(file.uri, file.name || "calisma.pdf", file.file);
      Alert.alert("Yüklendi", "Klinik çalışma başarıyla indekslendi ve sorularda kullanılabilir.");
      loadDocumentCount();
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsUploading(false);
    }
  }

  async function handleSend() {
    const question = input.trim();
    if (!question || isSending) return;

    const userMessage: ChatMessage = { id: `${Date.now()}-user`, role: "user", text: question };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsSending(true);

    try {
      const response = await askAssistant(question);
      const assistantMessage: ChatMessage = {
        id: `${Date.now()}-assistant`,
        role: "assistant",
        text: response.answer,
        sources: response.sources,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-error`, role: "assistant", text: apiErrorMessage(e) },
      ]);
    } finally {
      setIsSending(false);
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={90}
    >
      {user?.role === "admin" && (
        <View style={styles.adminBar}>
          <Text style={styles.adminBarText}>
            {documentCount === null ? "Klinik çalışmalar yükleniyor..." : `${documentCount} klinik çalışma indekslendi`}
          </Text>
          <TouchableOpacity style={styles.adminUploadButton} onPress={handleUploadDocument} disabled={isUploading}>
            {isUploading ? (
              <ActivityIndicator size="small" color={colors.primary} />
            ) : (
              <>
                <Icon name="upload" size={12} color={colors.primary} />
                <Text style={styles.adminUploadText}>Çalışma Yükle</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      )}

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.scrollContent}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        renderItem={({ item }) => <MessageBubble message={item} />}
      />

      {isSending && (
        <View style={styles.typingRow}>
          <ActivityIndicator size="small" color={colors.primary} />
          <Text style={styles.typingText}>Literatür taranıyor...</Text>
        </View>
      )}

      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="Ürün veya hastalık hakkında sorun..."
          placeholderTextColor={colors.textMuted}
          multiline
        />
        <TouchableOpacity style={styles.sendButton} onPress={handleSend} disabled={isSending}>
          <Icon name="send" size={18} color={colors.onPrimary} />
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <View style={[styles.bubbleRow, isUser && styles.bubbleRowUser]}>
      <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}>
        {!isUser && (
          <View style={styles.bubbleHeader}>
            <View style={styles.sparkBadge}>
              <Icon name="sparkles" size={14} color={colors.primary} />
            </View>
            <Text style={styles.bubbleBrand}>Klinik Asistan</Text>
          </View>
        )}
        <Text style={[styles.bubbleText, isUser && styles.bubbleTextUser]}>{message.text}</Text>
        {message.sources && message.sources.length > 0 && (
          <View style={styles.sourcesBox}>
            <Text style={styles.sourcesTitle}>Kaynaklar</Text>
            {message.sources.map((s, idx) => (
              <TouchableOpacity
                key={idx}
                disabled={!s.url}
                onPress={() => s.url && Linking.openURL(s.url)}
                style={styles.sourceRow}
              >
                <View style={styles.sourceIcon}>
                  <Icon name={s.type === "pubmed" ? "file" : "folder"} size={12} color={colors.textMuted} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.sourceTitle, !!s.url && styles.sourceLink]} numberOfLines={2}>
                    {s.title}
                  </Text>
                  {s.detail && <Text style={styles.sourceDetail}>{s.detail}</Text>}
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  scrollContent: { ...contentColumn, padding: layout.screenPadding },
  container: { flex: 1, backgroundColor: colors.background },
  adminBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing(1),
    paddingHorizontal: layout.screenPadding,
    paddingVertical: spacing(1.5),
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
  },
  adminBarText: { ...typography.meta, color: colors.textMuted, flex: 1 },
  adminUploadButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: colors.primaryTint,
    borderRadius: radius.sm,
    paddingHorizontal: spacing(1.5),
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: colors.primary,
    borderStyle: "dashed",
  },
  adminUploadText: { ...typography.meta, color: colors.primary, fontWeight: "700" },

  bubbleRow: { marginBottom: layout.cardGap, alignItems: "flex-start" },
  bubbleRowUser: { alignItems: "flex-end" },
  bubble: { maxWidth: "85%", borderRadius: radius.lg, padding: layout.cardPadding },
  bubbleAssistant: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  bubbleUser: { backgroundColor: colors.primary },
  bubbleHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(1),
    marginBottom: layout.cardGap,
  },
  sparkBadge: {
    width: 24,
    height: 24,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primaryTint,
  },
  bubbleBrand: { ...typography.bodyStrong, color: colors.primary },
  bubbleText: { color: colors.text, fontSize: 14, lineHeight: 21 },
  bubbleTextUser: { color: colors.onPrimary },

  sourcesBox: {
    marginTop: layout.cardGap,
    borderTopWidth: 1,
    borderTopColor: colors.borderSubtle,
    paddingTop: spacing(1),
  },
  sourcesTitle: {
    ...typography.badge,
    color: colors.textDim,
    marginBottom: spacing(0.5),
    textTransform: "uppercase",
  },
  sourceRow: { flexDirection: "row", marginTop: spacing(0.75) },
  sourceIcon: { marginRight: spacing(1), marginTop: 1 },
  sourceTitle: { color: colors.text, fontSize: 12, fontWeight: "600" },
  sourceLink: { color: colors.primary, textDecorationLine: "underline" },
  sourceDetail: { ...typography.meta, color: colors.textMuted, marginTop: 1 },

  typingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing(1),
    paddingHorizontal: layout.screenPadding,
    paddingBottom: spacing(1),
  },
  typingText: { ...typography.meta, color: colors.textMuted },

  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing(1.5),
    padding: layout.screenPadding,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  input: {
    flex: 1,
    minHeight: 48,
    maxHeight: 120,
    backgroundColor: colors.card,
    borderRadius: radius.md,
    paddingHorizontal: layout.cardPadding,
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  sendButton: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
  },
});
