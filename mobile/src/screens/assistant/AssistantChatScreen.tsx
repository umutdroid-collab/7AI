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
import { colors, spacing } from "../../theme";
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
              <Text style={styles.adminUploadText}>📤 Çalışma Yükle</Text>
            )}
          </TouchableOpacity>
        </View>
      )}

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => m.id}
        contentContainerStyle={{ padding: spacing(2) }}
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
          <Text style={styles.sendButtonText}>Gönder</Text>
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
                <Text style={styles.sourceIcon}>{s.type === "pubmed" ? "📄" : "📚"}</Text>
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
  container: { flex: 1, backgroundColor: colors.background },
  adminBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1),
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
  },
  adminBarText: { color: colors.textMuted, fontSize: 12, flex: 1 },
  adminUploadButton: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: 8,
    paddingHorizontal: spacing(1.5),
    paddingVertical: spacing(0.75),
    borderWidth: 1,
    borderColor: colors.border,
  },
  adminUploadText: { color: colors.primary, fontSize: 12, fontWeight: "700" },
  bubbleRow: { marginBottom: spacing(1.5), alignItems: "flex-start" },
  bubbleRowUser: { alignItems: "flex-end" },
  bubble: { maxWidth: "85%", borderRadius: 14, padding: spacing(1.5) },
  bubbleAssistant: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  bubbleUser: { backgroundColor: colors.primary },
  bubbleText: { color: colors.text, fontSize: 14, lineHeight: 20 },
  bubbleTextUser: { color: "#0f172a" },
  sourcesBox: { marginTop: spacing(1.5), borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingTop: spacing(1) },
  sourcesTitle: { color: colors.textMuted, fontSize: 11, fontWeight: "700", marginBottom: spacing(0.5), textTransform: "uppercase" },
  sourceRow: { flexDirection: "row", marginTop: spacing(0.5) },
  sourceIcon: { marginRight: spacing(1) },
  sourceTitle: { color: colors.text, fontSize: 12, fontWeight: "600" },
  sourceLink: { color: colors.primary, textDecorationLine: "underline" },
  sourceDetail: { color: colors.textMuted, fontSize: 11, marginTop: 1 },
  typingRow: { flexDirection: "row", alignItems: "center", paddingHorizontal: spacing(2), paddingBottom: spacing(1) },
  typingText: { color: colors.textMuted, fontSize: 12, marginLeft: spacing(1) },
  inputRow: {
    flexDirection: "row",
    padding: spacing(1.5),
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    alignItems: "flex-end",
  },
  input: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 20,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.25),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    maxHeight: 120,
  },
  sendButton: {
    backgroundColor: colors.primary,
    borderRadius: 20,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.25),
    marginLeft: spacing(1),
  },
  sendButtonText: { color: "#0f172a", fontWeight: "700" },
});
